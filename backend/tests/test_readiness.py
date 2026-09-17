from datetime import datetime
from app.services.readiness import assess
from app.services.data_evidence import SH

def ok(payload):return {'status':'ready','payload':payload}

def test_nonempty_wrong_date_limits_and_incomplete_minutes_never_ready():
 day='2026-09-16'
 ev={'limit_prices:000001':ok([{'t':'2026-09-14','h':11,'l':9}]),'minute_5:000001':ok([{'t':day+' 09:35:00','o':10,'h':11,'l':9,'c':10,'v':1,'sf':0}])}
 report=assess(day,ev,datetime(2026,9,17,10,tzinfo=SH));items={i['key']:i for i in report['items']}
 assert items['limits']['status']=='missing' and items['minute']['status']=='missing'
 assert '0/1' in items['limits']['value']

def test_minute_sample_and_actual_quote_time_not_fetch_time():
 day='2026-09-17';times=['09:35:00','09:40:00','09:45:00','09:50:00','09:55:00','10:00:00']
 ev={'basic_stock_list':ok([{'dm':'000001.SZ'}]),'minute_5:000001':ok([{'t':day+' '+t,'o':10,'h':11,'l':9,'c':10,'v':1,'sf':0} for t in times]),'market_snapshot_all':ok([{'dm':'000001','t':day+' 09:30:00','p':10,'o':9,'pc':1,'cje':100,'lb':1}])}
 report=assess(day,ev,datetime(2026,9,17,10,5,tzinfo=SH));items={i['key']:i for i in report['items']}
 assert items['minute']['status']=='ready'
 assert items['quote']['status']=='partial' and '过期' in items['quote']['detail']

def test_one_fresh_quote_cannot_hide_other_stale_quotes():
 day='2026-09-17';base={'p':10,'o':9,'pc':1,'cje':100,'lb':1}
 ev={'basic_stock_list':ok([{'dm':'000001'},{'dm':'000002'}]),'market_snapshot_all':ok([{**base,'dm':'000001','t':day+' 09:30:00'},{**base,'dm':'000002','t':day+' 10:05:00'}])}
 quote=next(i for i in assess(day,ev,datetime(2026,9,17,10,5,tzinfo=SH))['items'] if i['key']=='quote')
 assert quote['status']=='partial' and '1/2' in quote['detail']
