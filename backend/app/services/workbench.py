"""Independent workbench: audited evidence, explainable screens, frozen plans.
Read endpoints never fetch the vendor. No order execution lives in this module.
"""
import asyncio
import json
import math
import uuid
from datetime import date, datetime
from app.database import engine
from sqlalchemy import text
from app.liangmai.client import liangmai
from app.liangmai.parsing import records, snapshot_records, number, source_date, emotion_for_date, dragon_records
from app.services.data_evidence import SH, freshness

API_INFO = {
 'basic_stock_list': ('A股证券列表','股票范围核验','基础资料'),
 'basic_trade_calendar': ('交易日历','交易日定位','按年'),
 'market_snapshot_all': ('全市场快照','价格 / 成交额 / 量比 / 换手','盘中每分钟'),
 'stockpool_limit_up': ('涨停池','连板与行业线索','按交易日'),
 'stockpool_limit_down': ('跌停池','风险观察','按交易日'),
 'stockpool_broken_board': ('炸板池','分歧观察','按交易日'),
 'stockpool_strong': ('强势股池','候选范围','按交易日'),
 'auction_morning_grab_amount': ('早盘抢筹','竞价候选与抢筹金额','约09:26后'),
 'auction_morning_sector_pro': ('增强竞价板块','竞价方向','约09:26后'),
 'anomaly_emotion_cycle': ('情绪周期','复盘背景','按日核验'),
 'anomaly_popularity_rank': ('人气排行','关注度参考，不计入价格信号','当前榜单'),
 'lhb_daily': ('龙虎榜','盘后资金行为','盘后'),
 'sector_plate_code': ('板块目录','目录完整性核验','基础资料'),
 'flow_stock_history': ('个股资金历史','单股样本核验，暂不计分','按交易日'),
 'kline_history': ('前复权日线','MA20 / MA60 / 趋势','15:30—17:10更新'),
}
RULE_VERSION='workbench-v1.0'
TASKS=set()
COLLECT_LOCK=asyncio.Lock()

async def save_evidence(api,day,result):
    payload=result.get('data')
    if api=='anomaly_emotion_cycle':
        item=emotion_for_date(payload,day)
        payload=[item] if item else []
    count=len(payload) if isinstance(payload,(list,dict)) else 0
    status=('local' if result.get('_local') else 'ready') if result.get('ok') and count else 'empty' if result.get('ok') else 'error'
    # Only normalized safe client message is stored. Never serialize HTTP requests or credentials.
    async with engine.begin() as c:
        await c.execute(text('''INSERT INTO wb_evidence(api,trade_date,status,payload,row_count,message)
            VALUES(:api,:day,:status,CAST(:payload AS JSONB),:count,:message)
            ON CONFLICT(api,trade_date) DO UPDATE SET status=EXCLUDED.status,payload=EXCLUDED.payload,
            row_count=EXCLUDED.row_count,message=EXCLUDED.message,fetched_at=now()'''),
            dict(api=api,day=day,status=status,payload=json.dumps(payload,ensure_ascii=False),count=count,
                 message=result.get('msg','')))
    return {'api':api,'status':status,'rows':count,'message':result.get('msg','')}

async def evidence(day):
    async with engine.connect() as c:
        rows=(await c.execute(text('SELECT * FROM wb_evidence WHERE trade_date=:d'),{'d':day})).mappings().all()
    return {r['api']:dict(r) for r in rows}


def code_of(r):
    code=str(r.get('code') or r.get('dm') or r.get('c') or r.get('thsCode') or '').split('.')[0]
    return code if len(code)==6 and code.isdigit() else None

def value(r,*keys):
    for k in keys:
        if r.get(k) is not None:return number(r[k])
    return None

def factor(label,points,maximum,value_text):
    return {'label':label,'points':None if points is None else round(points,1),'max':maximum,'value':value_text}

def score_short(row,phase):
    if phase=='pre':
        amt=row.get('auction_amount'); pct=row.get('auction_pct'); order=row.get('auction_order')
        fs=[factor('抢筹成交额',min(max(amt,0)/5e7,1)*40 if amt is not None else None,40,amt),
            factor('抢筹涨幅',min(max(pct,0)/5,1)*30 if pct is not None else None,30,pct),
            factor('委托金额',min(max(order,0)/1e8,1)*30 if order is not None else None,30,order)]
    else:
        amt=row.get('amount'); vr=row.get('volume_ratio'); pct=row.get('pct_chg'); p=row.get('price'); o=row.get('open')
        fs=[factor('成交活跃',min(max(amt,0)/5e8,1)*30 if amt is not None else None,30,amt),
            factor('量比',min(max(vr,0)/3,1)*25 if vr is not None else None,25,vr),
            factor('涨幅强度',min(max(pct,0)/5,1)*25 if pct is not None else None,25,pct),
            factor('开盘承接',20 if p>=o else 0,20,'站上开盘价' if p>=o else '低于开盘价') if p is not None and o is not None else factor('开盘承接',None,20,None)]
    return fs

def trend_factors(row,bars,cutoff,sessions=None):
    # Never use target day's incomplete daily candle for trend factors.
    clean={source_date(b.get('t')):b for b in records(bars) if source_date(b.get('t')) and source_date(b.get('t'))<=cutoff
           and value(b,'c') is not None and value(b,'c')>0 and value(b,'h') is not None and value(b,'h')>0}
    bs=[clean[k] for k in sorted(clean)]
    expected=set((sessions or [])[-65:])
    missing_sessions=expected-set(clean)
    if missing_sessions or len(bs)<65 or not bs or source_date(bs[-1]['t'])!=cutoff or row.get('price') is None:
        return [], {'bars':len(bs),'latest':source_date(bs[-1]['t']) if bs else None,'required':65,'cutoff':cutoff,'missing_sessions_count':len(missing_sessions)}
    closes=[value(b,'c') for b in bs]; ma20=sum(closes[-20:])/20;ma60=sum(closes[-60:])/60
    before=sum(closes[-25:-5])/20; high20=max(value(b,'h') for b in bs[-20:]);p=row['price']
    return [factor('均线排列',30 if ma20>ma60 else 0,30,f'MA20 {ma20:.2f} / MA60 {ma60:.2f}'),
            factor('价格位置',25 if p>ma20 else 0,25,f'价格 {p:.2f} / MA20 {ma20:.2f}'),
            factor('均线方向',25 if ma20>before else 0,25,'MA20较五日前上升' if ma20>before else 'MA20未上升'),
            factor('20日突破',20 if p>high20 else 0,20,f'前20日最高 {high20:.2f}')], {'bars':len(bs),'latest':cutoff,'ma20':round(ma20,2),'ma60':round(ma60,2),'high20':high20}

async def build(day,phase='live',mode='short'):
    from app.services.research import entry_policy
    ev=await evidence(day)
    def data(api):return ev.get(api,{}).get('payload') if ev.get(api,{}).get('status') in ('ready','local') else []
    cal=(data('basic_trade_calendar') or [])+(data('calendar_previous_year') or [])
    days=sorted(d for raw in cal if (d:=source_date(raw)) and d<day) if isinstance(cal,list) else []
    previous=days[-1] if days else None
    context=await evidence(previous) if phase=='pre' and previous else ev if phase!='pre' else {}
    def context_data(api):return context.get(api,{}).get('payload') if context.get(api,{}).get('status') in ('ready','local') else []
    pool=records(context_data('stockpool_limit_up')); strong=records(context_data('stockpool_strong'))
    pool_map={code_of(r):r for r in pool}; strong_map={code_of(r):r for r in strong}
    auctions={code_of(r):r for r in records(data('auction_morning_grab_amount')) if source_date(r.get('time'))==day}
    dragon_codes={code_of(r) for r in dragon_records(context_data('lhb_daily'))}
    pop={code_of(r):r for r in records(data('anomaly_popularity_rank'))} if phase!='pre' else {}
    identities={code_of(r):r for r in records(data('basic_stock_list'))}
    universe=set(identities)
    rows=[]
    candidates=list(auctions.values()) if phase=='pre' else snapshot_records(data('market_snapshot_all'))
    for r in candidates:
        code=code_of(r)
        if not code or code not in universe:continue
        if phase!='pre' and source_date(r.get('t'))!=day:continue
        if not code.startswith(('00','30','60','68','43','83','87','88','92')):continue
        p=pool_map.get(code) or strong_map.get(code) or {};a=auctions.get(code,{});popular=pop.get(code,{})
        row={'code':code,'name':r.get('mc') or r.get('name') or r.get('n') or identities.get(code,{}).get('mc') or code,
             'industry':p.get('hy') or p.get('hybk') or p.get('industry') or '未归类',
             'price':None if phase=='pre' else value(r,'p','price'),
             'pct_chg':None if phase=='pre' else value(r,'pc','pct_chg'),
             'amount':None if phase=='pre' else value(r,'cje','amount'),
             'volume_ratio':None if phase=='pre' else value(r,'lb','volume_ratio'),
             'turnover':None if phase=='pre' else value(r,'hs','turnover'),
             'open':None if phase=='pre' else value(r,'o','open'),
             'source_at':None if phase=='pre' else r.get('t'),
             'auction_pct':value(a,'qczf'),'auction_amount':value(a,'qccje'),'auction_order':value(a,'qcwtje'),
             'consecutive':value(p,'Lbc','lbc','consecutive'),
             'in_pool':code in pool_map,'strong':code in strong_map,
             'popularity':value(popular,'order'), 'tags':popular.get('tag',{}).get('concept_tag',[]) if isinstance(popular.get('tag'),dict) else []}
        if phase=='pre':
            row['tags']=[label for cond,label in [(code in pool_map,'前日涨停'),(code in strong_map,'前日强势'),(code in dragon_codes,'前日龙虎榜')] if cond]
        if row['open'] is not None and row['open']<=0:row['open']=None
        if phase=='pre' and mode=='trend' and previous:
            old=[b for b in records(data('kline_history:'+code)) if source_date(b.get('t'))==previous]
            row['price']=value(old[-1],'c') if old else None
        row['freshness']=freshness(row['source_at'],day) if phase!='pre' else {'state':'auction','label':'早盘抢筹截面'}
        fs,trend=trend_factors(row,data('kline_history:'+code),previous,days) if mode=='trend' and previous else ([],{})
        if mode=='short':fs=score_short(row,phase)
        row['factors']=fs;row['trend']=trend
        known=sum(f['max'] for f in fs if f['points'] is not None)
        row['coverage']=known;row['score']=round(sum(f['points'] for f in fs),1) if fs and known==100 else None
        if phase!='pre' and row['freshness']['state'] in ('invalid','unknown','mismatch'):row['score']=None
        row['risks']=[]
        if 'ST' in row['name'].upper() or '退' in row['name']:row['risks'].append('风险名称标记')
        if row['in_pool']:row['risks'].append('涨停池标的，成交可得性需核验')
        if row['turnover'] is not None and row['turnover']>25:row['risks'].append('高换手')
        if mode=='trend' and not fs:row['risks'].append('历史不足或未更新，暂不评分')
        if phase!='pre' and row['freshness']['state']!='fresh':row['risks'].append(row['freshness']['label'])
        rows.append(row)
    rows.sort(key=lambda r:(r['score'] is not None,r['score'] or 0,r['amount'] or r['auction_amount'] or 0),reverse=True)
    industries={}
    for p in pool:
        label=p.get('hy') or p.get('hybk') or p.get('industry') or '未归类';industries[label]=industries.get(label,0)+1
    health=[]
    for api,(name,use,timing) in API_INFO.items():
        if api=='kline_history':
            matched=[v for k,v in ev.items() if k.startswith('kline_history:')]
            health.append({'api':api,'name':name,'use':use,'timing':timing,'status':'ready' if any(v['status'] in ('ready','local') for v in matched) else 'untested','rows':sum(v['row_count'] for v in matched),'sample_stocks':len(matched)})
        else:
            e=ev.get(api,{})
            health.append({'api':api,'name':name,'use':use,'timing':timing,'status':e.get('status','untested'),'rows':e.get('row_count',0),'fetched_at':e.get('fetched_at'),'message':e.get('message','')})
    emotion=records(data('anomaly_emotion_cycle'));dragon=dragon_records(data('lhb_daily'))
    return {'entry_policy':entry_policy(day,is_trade_day=day in {source_date(d) for d in cal}),'date':day,'is_trade_day':day in {source_date(d) for d in cal},'phase':phase,'mode':mode,'previous_date':previous,'context_date':previous if phase=='pre' else day,'rows':rows,'total':len(rows),
            'scored':sum(r['score'] is not None for r in rows),'health':health,'rule_version':RULE_VERSION,
            'market':{'up':sum((r['auction_pct' if phase=='pre' else 'pct_chg'] or 0)>0 for r in rows) if rows else None,'down':sum((r['auction_pct' if phase=='pre' else 'pct_chg'] or 0)<0 for r in rows) if rows else None,
                      'limit_up':len(pool) if context.get('stockpool_limit_up',{}).get('status') in ('ready','local') else None,
                      'limit_down':len(records(context_data('stockpool_limit_down'))) if context.get('stockpool_limit_down',{}).get('status') in ('ready','local') else None,
                      'broken':len(records(context_data('stockpool_broken_board'))) if context.get('stockpool_broken_board',{}).get('status') in ('ready','local') else None,
                      'amount':sum(r['auction_amount' if phase=='pre' else 'amount'] or 0 for r in rows) if rows else None,'emotion':emotion[0] if emotion else None,'dragon_count':len(dragon)},
            'industries':[{'name':k,'count':v} for k,v in sorted(industries.items(),key=lambda x:x[1],reverse=True)[:12]],
            'auction_sectors':records(data('auction_morning_sector_pro'))[:20],
            'quote_time':ev.get('market_snapshot_all',{}).get('fetched_at'),
            'note':'规则分用于排序，不是上涨概率。短线与趋势分别计算；缺字段不补零、不按剩余权重放大。'}

async def local_fallback(api,day,failure):
    """Fallback only to same-date known evidence; expose it as local, never fresh upstream."""
    old=(await evidence(day)).get(api,{})
    payload=old.get('payload') if old.get('status') in ('ready','local') else None
    if not payload and api in ('lhb_daily','anomaly_emotion_cycle'):
        from fastapi.encoders import jsonable_encoder
        async with engine.connect() as c:
            if api=='lhb_daily':
                rows=(await c.execute(text('SELECT trade_date, code, name, net_amount, buy_amount, sell_amount FROM dragon_tiger WHERE trade_date=:d'),{'d':day})).mappings().all()
                payload=jsonable_encoder([dict(r) for r in rows])
            else:
                r=(await c.execute(text('SELECT trade_date, emotion_score, limit_up_count, limit_down_count, seal_rate FROM emotion_cycle WHERE trade_date=:d'),{'d':day})).mappings().first()
                if r:payload=[{'date1':day,'dmqx':r['emotion_score'],'ztjs':r['limit_up_count'],'dtjs':r['limit_down_count'],'dbcgl':r['seal_rate']}]
    if payload:
        return {'ok':True,'data':payload,'_local':True,'msg':'上游本次失败，使用同日期本地证据；不代表接口本次成功'}
    return failure


async def update_job(job,results,total,finished=False):
    async with engine.begin() as c:
        await c.execute(text('''UPDATE wb_jobs SET progress=:p, results=CAST(:r AS JSONB),status=:s,
            finished_at=CASE WHEN :done THEN now() ELSE NULL END WHERE id=:id'''),
            {'p':len(results),'r':json.dumps(results,ensure_ascii=False),'s':'done' if finished else 'running','done':finished,'id':job})

async def collect(job,day,stage,codes):
    results=[]
    async with COLLECT_LOCK:
        try:
            if stage=='history':
                ev=await evidence(day);cal=(ev.get('basic_trade_calendar',{}).get('payload') or [])+(ev.get('calendar_previous_year',{}).get('payload') or [])
                previous=max((source_date(d) for d in cal if source_date(d) and source_date(d)<day),default=None)
                if not previous:raise ValueError('请先采集交易日历')
                calls=[('kline_history:'+code,'kline_history',{'full_code':code,'interval':'d','cq':'f','lt':100,'et':previous.replace('-','')}) for code in codes]
            elif stage=='quote':
                calls=[('market_snapshot_all','market_snapshot_all',{})]
            else:
                calls=[('basic_trade_calendar','basic_trade_calendar',{'year':day[:4]}),('basic_stock_list','basic_stock_list',{})]
                if day[5:7]=='01':
                    # Previous December is needed to identify the previous session in early January.
                    prior=await liangmai.call('basic_trade_calendar',{'year':str(int(day[:4])-1)},ttl=3600)
                    await save_evidence('calendar_previous_year',day,prior)
                if stage=='review' and day[5:7]=='12':
                    prior=await liangmai.call('basic_trade_calendar',{'year':str(int(day[:4])+1)},ttl=3600)
                    await save_evidence('calendar_next_year',day,prior)
                if stage!='pre':
                    calls.extend((api,api,{'trade_date':day}) for api in ['stockpool_limit_up','stockpool_limit_down','stockpool_broken_board','stockpool_strong'])
                if day==datetime.now(SH).date().isoformat() and stage!='pre':
                    calls.extend([(api,api,{}) for api in ['market_snapshot_all','anomaly_popularity_rank']])
                if stage in ('pre','live'):
                    calls.extend([('auction_morning_grab_amount','auction_morning_grab_amount',{'tradeDate':day,'period':'0','type':'1'}),('auction_morning_sector_pro','auction_morning_sector_pro',{'tradeDate':day})])
                if stage=='review':calls.extend([('anomaly_emotion_cycle','anomaly_emotion_cycle',{}),('lhb_daily','lhb_daily',{'date':day})])
            async with engine.begin() as c:await c.execute(text('UPDATE wb_jobs SET total=:n WHERE id=:id'),{'n':len(calls),'id':job})
            for key,api,params in calls:
                r=await liangmai.call(api,params,ttl=0)
                if not r.get('ok'):r=await local_fallback(key,day,r)
                item=await save_evidence(key,day,r);results.append(item)
                await update_job(job,results,len(calls))
                if stage=='pre' and api=='basic_trade_calendar' and r.get('ok'):
                    prev=max((source_date(d) for d in r.get('data',[]) if source_date(d) and source_date(d)<day),default=None)
                    if prev:
                        for base_api in ('stockpool_limit_up','stockpool_limit_down','stockpool_broken_board','stockpool_strong','lhb_daily'):
                            base=await liangmai.call(base_api,{'date' if base_api=='lhb_daily' else 'trade_date':prev},ttl=3600)
                            if not base.get('ok'):base=await local_fallback(base_api,prev,base)
                            base_item=await save_evidence(base_api,prev,base)
                            base_item['date']=prev;results.append(base_item)
                            async with engine.begin() as c:await c.execute(text('UPDATE wb_jobs SET total=total+1 WHERE id=:id'),{'id':job})
                            await update_job(job,results,0)
            await update_job(job,results,len(calls),True)
        except Exception:
            # Do not persist raw exception text (may contain URLs or connection details).
            results.append({'status':'error','message':'采集未完成，请检查数据源状态、日期和数据库'})
            async with engine.begin() as c:
                await c.execute(text("UPDATE wb_jobs SET status='failed',results=CAST(:r AS JSONB),finished_at=now() WHERE id=:id"),{'id':job,'r':json.dumps(results,ensure_ascii=False)})

async def start_job(day,stage,codes):
    async with engine.begin() as c:
        # Serialize admissions, including across HTTP workers. Expired jobs may be retried.
        await c.execute(text("SELECT pg_advisory_xact_lock(889919009)"))
        active=(await c.execute(text("SELECT id FROM wb_jobs WHERE status='running' AND created_at>now()-interval '20 minutes' LIMIT 1"))).scalar()
        if active:return {'ok':False,'message':'已有采集任务正在执行','job_id':active}
        job=uuid.uuid4().hex
        await c.execute(text("INSERT INTO wb_jobs(id,status,stage,trade_date,total) VALUES(:id,'running',:stage,:d,0)"),{'id':job,'stage':stage,'d':day})
    task=asyncio.create_task(collect(job,day,stage,codes));TASKS.add(task);task.add_done_callback(TASKS.discard)
    return {'ok':True,'job_id':job}


async def recover_jobs():
    """Single-worker deployment: interrupted jobs must not remain running forever."""
    async with engine.begin() as c:
        await c.execute(text("""UPDATE wb_jobs SET status='failed',finished_at=now(),
            results=results || '[{"status":"error","message":"服务重启中断了采集，请重新同步"}]'::jsonb
            WHERE status='running'"""))
