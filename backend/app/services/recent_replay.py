"""Fixed-rule, timestamped morning replay; simulated fills, never actual trades."""
from app.liangmai.parsing import number,source_date
from app.services.workbench import score_short,code_of

POLICY={'version':'morning-replay-v1','max_candidates':3,'score_min':60,'auction_pct_min':1,'auction_pct_max':8,
        'entry_time':'09:40','budget_per_trade':10000,'commission_rate':0.0003,'minimum_commission':5,
        'transfer_rate':0.00001,'sell_stamp_rate':0.0005,'slippage_each_side':0.001,'holds':[1,2,3]}

def choose_candidates(auction,day,hot_codes):
    picked={}
    for r in auction:
        code=code_of(r);name=str(r.get('name') or code);pct=number(r.get('qczf'))
        if not code or not code.startswith(('00','60')) or 'ST' in name.upper() or '退' in name:continue
        if source_date(r.get('time'))!=day or code not in hot_codes or pct is None or not 1<=pct<=8:continue
        row={'auction_amount':number(r.get('qccje')),'auction_pct':pct,'auction_order':number(r.get('qcwtje'))}
        fs=score_short(row,'pre')
        if any(f['points'] is None for f in fs):continue
        score=round(sum(f['points'] for f in fs),1)
        if score<60:continue
        picked[code]={'code':code,'name':name,'score':score,**row,'factors':fs,'signal_date':day}
    return sorted(picked.values(),key=lambda r:(-r['score'],-r['auction_amount'],r['code']))[:3]

def valid_bar(b):
    vals=[number(b.get(k)) for k in ('o','h','l','c')]
    return all(v is not None and v>0 for v in vals) and vals[2]<=min(vals[0],vals[3])<=max(vals[0],vals[3])<=vals[1] and number(b.get('sf'))==0 and (number(b.get('v')) or 0)>0

def confirmation_gate(day, minute_bars):
    """Same completed 09:35 bar gate for live observations and historical replay."""
    signal=next((b for b in minute_bars if str(b.get('t'))==day+' 09:35:00'),None)
    if not signal or not valid_bar(signal):
        return {'state':'unknown','reason':'缺少有效09:35已完成五分钟K线'}
    if number(signal['c'])<=number(signal['o']):
        return {'state':'rejected','reason':'09:35收盘未站上首根开盘价，不触发入场','bar':signal}
    return {'state':'confirmed','reason':'首根5分钟K线站上开盘价；等待09:40模拟参考与涨跌停核验','bar':signal}

def evaluate(candidate,calendar,minute_bars,daily_bars,limits,asof,policy=None):
    p=policy or POLICY;day=candidate['signal_date'];result={**candidate,'entry_status':'not_entered','paths':[]}
    minutes={str(b.get('t')):b for b in minute_bars}
    gate=confirmation_gate(day,minute_bars);entry=minutes.get(day+' 09:45:00')
    if gate['state']=='unknown':return result|{'entry_status':'unknown','reason':gate['reason']}
    if gate['state']=='rejected':return result|{'reason':gate['reason']}
    if not entry or not valid_bar(entry):return result|{'entry_status':'unknown','reason':'缺少有效09:40开始的下一根五分钟K线'}
    daily={source_date(b.get('t')):b for b in daily_bars};stops={source_date(b.get('t')):b for b in limits}
    stop=stops.get(day,{})
    upper=number(stop.get('h'));lower=number(stop.get('l'));price=number(entry['o'])
    if upper is None or lower is None:return result|{'entry_status':'unknown','reason':'缺少当日涨跌停价，不能核验入场'}
    if not lower<price<upper or number(entry['h'])==number(entry['l']):return result|{'reason':'参考入场价触及涨跌停或整根单一价格，不假定成交'}
    # Reference price fill plus separately charged cost stress, not a fabricated out-of-range fill price.
    shares=int(p['budget_per_trade']/price/100)*100
    def entry_cost(n):
        gross=n*price
        return gross+max(p['minimum_commission'],gross*p['commission_rate'])+gross*(p['transfer_rate']+p['slippage_each_side'])
    while shares and entry_cost(shares)>p['budget_per_trade']:shares-=100
    if shares<=0:return result|{'reason':'单笔一万元不足买入100股并支付费用'}
    cost=entry_cost(shares);result.update(entry_status='simulated',entry_date=day,entry_time='09:40',entry_price=price,shares=shares,entry_cost=round(cost,2),reason='按09:45结束K线的开盘价模拟09:40入场；成交未被逐笔核验')
    days=sorted({source_date(d) for d in calendar if source_date(d) and source_date(d)>day})
    for hold in p['holds']:
        path={'hold':hold,'status':'pending','exit_date':days[hold-1] if len(days)>=hold else None}
        exitday=path['exit_date']
        if exitday is None or exitday>asof:path['reason']='未到完整退出交易日';result['paths'].append(path);continue
        needed=[day]+days[:hold];reason=None
        for i,d in enumerate(needed):
            b=daily.get(d)
            if not b or not valid_bar(b):reason='区间日线缺失、停牌或价格无效';break
            if i and (number(b.get('pc')) is None or abs(number(b['pc'])-number(daily[needed[i-1]]['c']))>0.015):reason='前收盘价断裂或缺失，需核验除权';break
        if reason:path.update(status='unknown',reason=reason);result['paths'].append(path);continue
        b=daily[exitday];close=number(b['c']);down=number(stops.get(exitday,{}).get('l'))
        if down is None:path.update(status='unknown',reason='缺少退出日跌停价，不能核验卖出')
        elif close<=down or number(b['h'])==number(b['l']):path.update(status='blocked',reason='退出价触及跌停或单一价格，卖出未被证实，不记已实现收益')
        else:
            gross=close*shares;fees=max(p['minimum_commission'],gross*p['commission_rate'])+gross*(p['transfer_rate']+p['sell_stamp_rate']+p['slippage_each_side'])
            pnl=gross-fees-cost
            path.update(status='evaluated',exit_price=close,gross_pct=round((close/price-1)*100,3),net_pct=round(pnl/cost*100,3),pnl=round(pnl,2),total_costs=round(cost-price*shares+fees,2))
        result['paths'].append(path)
    return result

def filter_comparisons(trades):
    """Exploratory gates on the original top-three universe, without backfilling replacements."""
    presets=[('原规则',lambda t:True),('原前三名且评分≥80',lambda t:t.get('score',0)>=80),('原前三名且竞价涨幅≤5%',lambda t:t.get('auction_pct',99)<=5)]
    out=[]
    for name,accept in presets:
        group=[t for t in trades if accept(t)]
        paths=[p for t in group for p in t['paths'] if p['hold']==1 and p['status']=='evaluated'];n=len(paths)
        out.append({'name':name,'candidates':len(group),'evaluated':n,'win_rate':round(sum(p['pnl']>0 for p in paths)/n*100,1) if n else None,
                    'mean_net_pct':round(sum(p['net_pct'] for p in paths)/n,3) if n else None,
                    'unverified':sum(t['entry_status']=='unknown' for t in group),'not_entered':sum(t['entry_status']=='not_entered' for t in group)})
    return out
