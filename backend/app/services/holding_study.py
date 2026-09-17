"""Conservative daily-bar price-path study, never presented as broker executions."""
from app.liangmai.parsing import number, source_date

HOLDS=(1,2,3,5,10)
def evaluate_path(signal_day,calendar,bars):
    sessions=sorted({d for raw in calendar if (d:=source_date(raw)) and d>signal_day})
    if len(sessions)<11:return {'status':'excluded','reason':'后续交易日历不足'}
    byday={source_date(b.get('t')):b for b in bars}
    needed=sessions[:11]
    if any(d not in byday for d in needed):return {'status':'excluded','reason':'后续11个交易日日线不完整'}
    series=[byday[d] for d in needed]
    for i,b in enumerate(series):
        if any(number(b.get(k)) is None or number(b[k])<=0 for k in ('o','h','l','c')):return {'status':'excluded','reason':'OHLC缺失'}
        if number(b.get('sf'))!=0 or not number(b.get('v')) or number(b['v'])<=0:return {'status':'excluded','reason':'停牌字段或成交量不满足核验'}
        if not (number(b['l'])<=min(number(b['o']),number(b['c']))<=max(number(b['o']),number(b['c']))<=number(b['h'])):return {'status':'excluded','reason':'OHLC结构异常'}
        # Reject all one-price days without claiming an available fill from daily bars.
        if number(b['h'])==number(b['l']):return {'status':'excluded','reason':'单一价格日，无法证明可成交'}
        if i:
            pc=number(b.get('pc'));prev=number(series[i-1]['c'])
            if pc is None or abs(pc-prev)>0.015:return {'status':'excluded','reason':'前收盘价断裂或缺失，可能存在除权事件'}
    entry=number(series[0]['o']);out=[]
    for hold in HOLDS:
        close=number(series[hold]['c'])
        out.append({'hold':hold,'entry_date':needed[0],'exit_date':needed[hold],'entry_price':entry,'exit_price':close,'price_change_pct':round((close/entry-1)*100,4)})
    return {'status':'evaluated','paths':out,'assumption':'盘后信号，次日开盘价至买入后第N交易日收盘价；仅价格路径，未证明真实成交'}
