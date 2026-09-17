"""Local minute reconstruction helpers. Unknown data never means an automatic pass."""
import math

def feature(rows, until, prev_close, strict=True):
    rs=[r for r in rows if '09:30'<=str(r['time'])[:5]<=until and str(r['time'])<=until+':59' and r.get('price') and r['price']>0]
    if len(rs)<(1 if until=='09:31' else 3):return None
    if str(rs[-1]['time'])[:5]!=until:return None
    prices=[r['price'] for r in rs];op,last=prices[0],prices[-1];hi,lo=max(prices),min(prices)
    avg=rs[-1].get('avg')
    if not avg or not math.isfinite(avg) or avg<=0:
        if strict:return None
        avg=last
    return {'count':len(rs),'lastTime':rs[-1]['time'],'open':op,'last':last,'high':hi,'low':lo,'avg':avg,'aboveAvg':last>=avg,'endPct':round((last/op-1)*100,2),'highPct':round((hi/op-1)*100,2),'lowPct':round((lo/op-1)*100,2),'pctVsPrev':round((last/prev_close-1)*100,2) if prev_close else 0}

def record_exclusion(r):
    day=r['trade_date'];selected=str(r.get('selected_time') or '');created=str(r.get('created_at') or '')
    if not selected.startswith(day) or not created.startswith(day):return '事后回填或记录日期不符'
    if not ('09:30:00'<=selected[11:19]<'10:00:00'):return '不在09:30至10:00实际记录窗口'
    return None

def price_paths(entry, future, sessions):
    # Exact calendar dates; never skip suspended/missing sessions and shorten a holding period.
    if len(sessions)<5:return None
    needed=sessions[:5]
    if any(d not in future for d in needed):return None
    for d in needed:
        b=future[d]
        if not all(b.get(k) and math.isfinite(b[k]) and b[k]>0 for k in ('open','high','low','close','volume')):return None
        if not b['low']<=min(b['open'],b['close'])<=max(b['open'],b['close'])<=b['high'] or b['high']==b['low']:return None
    return [{'hold':h,'exit_date':needed[h-1],'exit_price':future[needed[h-1]]['close'],'price_change_pct':round((future[needed[h-1]]['close']/entry-1)*100,3)} for h in (1,3,5)]
