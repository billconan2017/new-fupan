from app.services.legacy_replay import feature, record_exclusion, price_paths
from app.services.legacy_rules.stage import _intraday_stage_status
from app.services.legacy_portfolio import report
import sqlite3


def test_feature_does_not_use_preopen_or_future_and_missing_avg_rejects():
    rows=[{'time':'09:29','price':1,'avg':1},{'time':'09:30','price':10,'avg':10},{'time':'09:31','price':10.1,'avg':None},{'time':'09:32','price':20,'avg':10}]
    assert feature(rows,'09:31',10) is None
    rows[2]['avg']=10
    f=feature(rows,'09:31',10)
    assert f['open']==10 and f['last']==10.1 and f['count']==2


def test_stale_minute_feature_rejected():
    assert feature([{'time':'09:30','price':10,'avg':10}],'09:31',10) is None


def test_record_time_must_be_actual_day_before_ten():
    base={'trade_date':'2026-06-05','selected_time':'2026-06-05 09:40:02','created_at':'2026-06-05 09:40:02'}
    assert record_exclusion(base) is None
    assert record_exclusion({**base,'created_at':'2026-06-21 09:40:02'})
    assert record_exclusion({**base,'selected_time':'2026-06-05 10:00:00'})


def test_tplus_uses_exact_sessions_not_next_available_bar():
    days=['2026-06-08','2026-06-09','2026-06-10','2026-06-11','2026-06-12']
    daily={d:dict(open=10,high=12,low=9,close=11,volume=100) for d in days}
    paths=price_paths(10,daily,days)
    assert paths[0]['exit_date']==days[0] and paths[-1]['exit_date']==days[-1]
    del daily[days[1]]
    assert price_paths(10,daily,days) is None


def test_legacy_rule_uses_injected_features_without_database():
    previous=dict(close=10,open=10,high=10.1,low=9.9,pct_chg=0)
    f=feature([{'time':'09:30','price':10,'avg':10},{'time':'09:31','price':10.1,'avg':10.05}],'09:31',10)
    assert _intraday_stage_status({'jjzf':1},previous,'945',lambda *a,**k:f)[0]=='早确认池'
    assert _intraday_stage_status({'jjzf':1},previous,'945',lambda *a,**k:None)[0]=='只观察'


def test_portfolio_missing_does_not_create_empty_database(tmp_path):
    path=tmp_path/'missing.db'
    assert report(path)['error']
    assert not path.exists()


def test_portfolio_reconciliation_preserves_source(tmp_path):
    p=tmp_path/'portfolio.db'
    with sqlite3.connect(p) as c:
        c.executescript('''CREATE TABLE holdings(id,code,name,cost,shares,buy_date,buy_time,status,stop_loss,take_profit,strategy_tags);
        CREATE TABLE trades(id,code,name,action,price,shares,trade_date,trade_time,profit,profit_pct);
        INSERT INTO holdings VALUES(1,'600000','测试',10,100,'2026-06-05','09:35','sold',NULL,NULL,NULL);
        INSERT INTO trades VALUES(1,'600000','测试','buy',10,100,'2026-06-05','09:35',NULL,NULL);''')
    before=p.read_bytes();r=report(p)
    assert r['reconciliation']==[{'code':'600000','ledger_net_shares':100,'holding_shares':0}]
    assert r['summary']['recorded_profit_sum'] is None
    assert p.read_bytes()==before
