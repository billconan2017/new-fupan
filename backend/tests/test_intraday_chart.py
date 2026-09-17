from app.services.intraday_chart import chart_data as build_chart
from app.services.data_evidence import SH
from datetime import datetime

def chart_data(*args,**kwargs):
    return build_chart(*args,now=datetime(2026,9,17,15,10,tzinfo=SH),**kwargs)

def bar(time,**kw):
    return dict(t='2026-09-17 '+time,o=10,h=11,l=9,c=10.2,v=100,a=1020,pc=10,**kw)

def test_intraday_rejects_wrong_dates_and_invalid_bars_without_filling_gaps():
    good=bar('09:35:00')
    bad=dict(good,t='2026-09-16 09:40:00')
    invalid=dict(good,t='2026-09-17 09:40:00',c=12)
    r=chart_data('2026-09-17',[good,bad,invalid,bar('09:45:00'),bar('12:00:00')],previous_close=10)
    assert [x['time'] for x in r['items']]==['09:35','09:45']
    assert r['previous_close']==10

def test_inconsistent_previous_close_is_not_drawn():
    r=chart_data('2026-09-17',[bar('09:35:00'),dict(bar('09:40:00'),pc=9)])
    assert r['previous_close'] is None

def test_missing_volume_does_not_invent_vwap():
    r=chart_data('2026-09-17',[dict(bar('13:05:00'),v=None,a=None)])
    assert r['items'][0]['v'] is None and 'vwap' not in r['items'][0]


def test_future_bar_and_previous_bar_close_are_not_today_evidence():
    r=build_chart('2026-09-17',[bar('09:35:00'),bar('09:40:00')],now=datetime(2026,9,17,9,36,tzinfo=SH))
    assert len(r['items'])==1 and r['previous_close'] is None
