from datetime import datetime
from app.services.data_evidence import freshness, quote_time, SH
from app.services.review_service import _calculate_score


def test_source_time_is_not_collection_time():
    now=datetime(2026,9,17,10,0,tzinfo=SH)
    assert quote_time('2026-09-17') is None
    assert freshness(None,'2026-09-17',now)['state']=='unknown'
    assert freshness('2026-09-17 09:59:00','2026-09-17',now)['state']=='fresh'
    assert freshness('2026-09-17 09:30:00','2026-09-17',now)['state']=='stale'
    assert freshness('2026-09-16 15:00:00','2026-09-17',now)['state']=='mismatch'
    assert freshness('2026-09-17 11:00:00','2026-09-17',now)['state']=='invalid'
    assert freshness('2026-09-16 15:00:00','2026-09-16',now)['state']=='history'
    assert quote_time('20260917095900').hour==9


def test_incomplete_report_is_not_neutral_and_zero_is_real():
    assert _calculate_score(*([{'available':False}]*7))[0] is None
    inputs=[{'available':True,'emotion_score':0}, {'available':True,'count':30},
            {'available':True,'count':1}, {'available':True,'count':1},
            {'available':True,'net_buy_total':1}, {'available':True,'total_main_net':1},
            {'available':True,'rise_ratio':50}]
    score0,_=_calculate_score(*inputs)
    inputs[0]['emotion_score']=50
    score50,_=_calculate_score(*inputs)
    assert score50-score0==10


def test_legacy_history_readonly_and_no_future_data(tmp_path):
    import sqlite3
    from app.services.legacy_history import read_daily
    path=tmp_path/'legacy.db'
    with sqlite3.connect(path) as c:
        c.execute('CREATE TABLE stock_daily_kline (code TEXT, trade_date TEXT, open REAL, high REAL, low REAL, close REAL, source TEXT)')
        c.executemany('INSERT INTO stock_daily_kline VALUES (?,?,?,?,?,?,?)',[
            ('000001','2026-09-16',10,12,9,11,'old'), ('000001','2026-09-17',11,13,10,12,'old'),
            ('000001','2026-09-15',10,8,9,11,'bad')])
    before=path.read_bytes()
    r=read_daily(str(path),'000001','2026-09-16')
    assert len(r['items'])==1 and r['latest_date']=='2026-09-16'
    assert r['rejected_rows']==1 and r['remote_calls']==0
    assert path.read_bytes()==before
    assert not read_daily(str(tmp_path/'absent.db'),'000001','2026-09-16')['ok']
    assert not (tmp_path/'absent.db').exists()
