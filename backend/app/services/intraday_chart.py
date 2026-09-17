"""Normalize actual five-minute closes. Never fabricate minute or VWAP values."""
from app.liangmai.parsing import records,number
from app.services.data_evidence import quote_time,SH
from datetime import datetime

def chart_data(day,payload,previous_close=None,now=None):
    now=now or datetime.now(SH)
    bars={}
    for r in records(payload):
        t=quote_time(r.get('t'))
        if not t or t.date().isoformat()!=day or t>now:continue
        hm=t.strftime('%H:%M')
        if not ('09:35'<=hm<='11:30' or '13:05'<=hm<='15:00'):continue
        if t.minute%5 or t.second:continue
        values={k:number(r.get(k)) for k in ('o','h','l','c','v','a','pc')}
        if any(values[k] is None or values[k]<=0 for k in ('o','h','l','c')):continue
        if values['l']>min(values['o'],values['c']) or values['h']<max(values['o'],values['c']):continue
        bars[hm]={'time':hm,'t':t.isoformat(),**values}
    items=[bars[k] for k in sorted(bars)]
    # Minute pc is the previous BAR close in observed payloads, not yesterday's close.
    prior=number(previous_close)
    return {'items':items,'previous_close':prior if prior and prior>0 else None,
            'interval':5,'note':'真实5分钟收盘点与成交量；不是逐笔分时。不插补缺点。成交量单位未经独立核验，暂不绘制VWAP均价线。'}
