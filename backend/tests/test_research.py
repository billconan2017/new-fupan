from datetime import datetime,date,timedelta
from app.services.research import trading_window,preparation_rows,entry_policy
from app.services.holding_study import evaluate_path
from app.services.data_evidence import SH

def test_t1_skips_weekend_and_holiday():
    calendar=['20260917','20260918','20260921','20260922']
    assert trading_window('2026-09-17',calendar)['earliest_sell_date']=='2026-09-21'
    assert trading_window('2026-09-18',calendar)['buy_date']=='2026-09-21'
    assert trading_window('2026-09-22',calendar)['buy_date'] is None

def test_duplicate_dragon_records_not_double_counted_and_st_excluded():
    ev={'stockpool_limit_up':{'status':'ready','payload':[{'dm':'000001','mc':'平安','hy':'银行','cje':123}]},'lhb_daily':{'status':'local','payload':[{'code':'000001','net_amount':100},{'code':'000001','net_amount':100},{'code':'000002','name':'ST测试'}]}}
    rows=preparation_rows(ev)
    assert len(rows)==1 and rows[0]['overlap']==2
    assert rows[0]['net_amount']==100 and rows[0]['dragon_records']==2

def test_cutoff_at_ten_and_historical_never_entry():
    day='2026-09-17'
    for hm,allowed in [('09:25',False),('09:26',False),('09:30',True),('09:59',True),('10:00',False),('14:00',False)]:
        assert entry_policy(day,datetime.fromisoformat(day+'T'+hm).replace(tzinfo=SH),is_trade_day=True)['entry_allowed']==allowed
    assert not entry_policy('2026-09-16',datetime(2026,9,17,9,35,tzinfo=SH))['entry_allowed']

def test_holding_paths_never_same_day_sell_and_common_cohort():
    dates=[(date(2026,1,1)+timedelta(days=i)).isoformat() for i in range(12)]
    bars=[{'t':d,'o':10,'c':10,'h':11,'l':9,'pc':10,'v':100,'sf':0} for d in dates[1:]]
    r=evaluate_path(dates[0],dates,bars)
    assert r['status']=='evaluated' and r['paths'][0]['exit_date']==dates[2]
    assert r['paths'][0]['entry_date']==dates[1]
    assert evaluate_path(dates[0],dates,bars[:-1])['status']=='excluded'
    bars[-1]['pc']=8
    assert '前收盘' in evaluate_path(dates[0],dates,bars)['reason']

def test_tick_date_wire_format_is_compact_but_other_dates_stay_iso():
    from app.liangmai.contracts import prepare
    for api in ('market_tick_history','market_tick_bj_history'):
        assert prepare(api,{'trade_date':'2026-09-16','ts_code':'600519'})[1]['trade_date']=='20260916'
        assert prepare(api,{'trade_date':'20260916','ts_code':'600519'})[1]['trade_date']=='20260916'
    assert prepare('stockpool_strong',{'trade_date':'2026-09-16'})[1]['trade_date']=='2026-09-16'

def test_preclose_collection_not_upgraded_to_final_just_because_clock_passes_close():
    from app.services.research import collected_after_close
    assert not collected_after_close('2026-09-17',{'p':{'fetched_at':'2026-09-17T11:30:00+08:00'}},['p'])
    assert collected_after_close('2026-09-17',{'p':{'fetched_at':'2026-09-17T17:11:00+08:00'}},['p'])
    assert not collected_after_close('2026-09-17',{},['p'])
