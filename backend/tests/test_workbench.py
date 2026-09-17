from datetime import date,timedelta
from app.services.workbench import score_short,trend_factors

def bars(n=70):
    return [{'t':(date(2025,1,1)+timedelta(days=i)).isoformat(),'c':10+i*.1,'h':10.2+i*.1,'o':9.9+i*.1,'l':9.8+i*.1} for i in range(n)]

def test_short_missing_not_zero_and_no_inflated_weights():
    fs=score_short({'amount':None,'volume_ratio':3,'pct_chg':5,'price':10,'open':9},'live')
    assert fs[0]['points'] is None
    fs=score_short({'amount':0,'volume_ratio':0,'pct_chg':-2,'price':9,'open':10},'live')
    assert sum(f['points'] for f in fs)==0
    fs=score_short({'auction_amount':5e7,'auction_pct':5,'auction_order':1e8},'pre')
    assert sum(f['points'] for f in fs)==100

def test_trend_no_future_no_stale_no_calendar_gaps():
    bs=bars();cutoff=bs[-1]['t'];sessions=[b['t'] for b in bs]
    fs,meta=trend_factors({'price':20},bs,cutoff,sessions)
    assert sum(f['points'] for f in fs)==100 and meta['bars']==70
    future=bars(71)[-1];future['c']=1000
    assert trend_factors({'price':20},bs+[future],cutoff,sessions)==(fs,meta)
    assert not trend_factors({'price':20},bs[:-1],cutoff,sessions)[0]
    assert not trend_factors({'price':20},bs[:20]+bs[21:],cutoff,sessions)[0]
    assert not trend_factors({'price':20},bs[-64:],cutoff,sessions)[0]
    assert not trend_factors({'price':None},bs,cutoff,sessions)[0]
