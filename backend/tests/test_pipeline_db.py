"""Opt-in integration suite; run only against a disposable PostgreSQL cluster."""
import os
from unittest.mock import AsyncMock
import httpx
import pytest
from sqlalchemy import text
from app.database import engine
from app.liangmai.client import liangmai

pytestmark=pytest.mark.skipif(os.environ.get('FUPAN_TEST_DB')!='1',reason='requires disposable PostgreSQL')


async def test_pipeline_inserts_and_health(monkeypatch):
    from app.services import pool_service, dragon_service, emotion_service, capital_service, auction_service
    from app.routers import kline
    from app.services.snapshot_scheduler import SnapshotScheduler
    from app.services.review_service import generate_review
    from app.main import app
    day='2026-09-16'
    async def upstream(api, params=None, ttl=0):
        values={
            'stockpool_limit_up':[{'dm':'000001','Mc':'平安银行','p':12,'Lbc':2}],
            'stockpool_limit_down':[{'dm':'000002','mc':'测试','p':8}],
            'stockpool_broken_board':[{'dm':'000003','mc':'测试','p':9}],
            'stockpool_strong':[{'dm':'000004','mc':'测试','p':10}],
            'lhb_daily':[{'thsCode':'000001','name':'平安银行','close':'12','buyAmount':'10','sellAmount':'3'}],
            'anomaly_emotion_cycle':{'colNameList':['date1','ztjs','dtjs','ylgd','lbjs','dbcgl'],'contentList':[[20260916,89,4,6,12,75]]},
            'flow_stock_history':[{'t':'2026-09-16','jlrcdcje':100,'jlrddcje':50,'jlrzdcje':-30,'jlrxdcje':-120}],
            'sector_plate_code':[{'plateCode':'BK1001','name':'测试行业'}],
            'flow_sector_history':[{'time':day,'mainAmount':'100','minAmount':'-50'}],
            'auction_morning_sector':[{'bkCode':'BK1001','bkName':'测试行业'}],
            'auction_morning_grab_amount':[{'code':'000001','name':'平安银行'}],
            'auction_one_word_limit':{'todayList':[{'code':'000001','name':'平安银行'}]},
            'auction_tail_grab_amount':[], 'auction_tail_grab_turnover':[],
            'auction_tail_grab_close':[], 'auction_tail_grab_change':[],
            'kline_history':[{'t':day,'o':11,'h':13,'l':10,'c':12,'v':100,'a':1200}],
        }
        assert api in values,api
        return {'ok':True,'code':0,'data':values[api],'_meta':{'api':api}}
    monkeypatch.setattr(liangmai,'call',upstream)
    try:
        pools=await pool_service.fetch_all_pools(day)
        assert all(r['ok'] and r['count']==1 for r in pools.values())
        assert (await dragon_service.fetch_dragon_tiger(day))['stocks']==1
        assert (await emotion_service.fetch_emotion_cycle(day))['ok']
        assert (await capital_service.fetch_capital_flow(day))['count']==1
        assert (await capital_service.fetch_sector_flow(day))['count']==1
        auction=await auction_service.fetch_all_auction(day)
        assert all(r['ok'] for r in auction.values())
        await kline._fetch_and_persist('000001','day',5)
        snapshot=SnapshotScheduler()
        await snapshot._batch_insert(day,day+' 15:00:00',[{'code':'000001','p':12,'pc':2}])
        async with engine.connect() as conn:
            assert (await conn.execute(text("SELECT COUNT(*) FROM stock_daily_kline"))).scalar()==1
            assert (await conn.execute(text("SELECT main_net FROM capital_flow WHERE code='000001'"))).scalar()==150
        report=await generate_review(day)
        assert report['ok']
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            health=await client.get('/api/data-quality/status',params={'date':day})
            assert health.status_code==200
            assert all(r['status']=='available' for r in health.json()['datasets'])
    finally:
        await engine.dispose()


async def test_cockpit_date_boundaries_and_missing_quotes():
    from app.routers.cockpit import summary
    from app.services.snapshot_scheduler import SnapshotScheduler
    from app.services.review_service import generate_review_snapshot
    from datetime import date
    try:
        async with engine.begin() as conn:
            await conn.execute(text("INSERT INTO limit_up_pool (trade_date,code,name,consecutive) VALUES ('2020-01-03','000001','历史样本',2),('2020-01-06','000001','历史样本',3),('2020-01-03','000002','缺报价',1)"))
        await SnapshotScheduler()._batch_insert('2020-01-06','2020-01-06 10:01:00',[
            {'code':'000001','p':12,'pc':2,'cje':123456789,'t':'2020-01-06 10:00:00'}])
        r=await summary(date(2020,1,6))
        assert r['baseline_date']=='2020-01-03'  # no calendar-day subtraction
        assert r['watchlist']['total']==2 and r['watchlist']['quoted']==1
        assert r['watchlist']['in_today_pool']==1
        assert r['watchlist']['items'][0]['quote_status']['state']=='history'
        assert r['watchlist']['items'][1]['price'] is None
        assert r['remote_calls']==0 and r['review']['overall_score'] is None
        old=await summary(date(2020,1,2))
        assert old['baseline_date'] is None and old['watchlist']['total']==0
        assert (await generate_review_snapshot('2020-01-02'))['report']['quality']['status']=='partial'
    finally:
        await engine.dispose()


async def test_workbench_frozen_plans_and_real_names():
    from app.services.workbench import save_evidence,build
    from app.main import app
    day='2025-03-12'
    def ok(data):return {'ok':True,'data':data,'msg':'ok'}
    try:
        await save_evidence('basic_stock_list',day,ok([{'dm':'000001.SZ','mc':'平安银行'}]))
        await save_evidence('basic_trade_calendar',day,ok(['20250311','20250312']))
        await save_evidence('market_snapshot_all',day,ok([{'dm':'000001','p':10,'pc':2,'o':9,'cje':5e8,'lb':3,'t':day+' 10:00:00'}, {'dm':'500001','p':1,'t':day+' 10:00:00'}]))
        await save_evidence('auction_morning_grab_amount',day,ok([{'code':'000001','name':'平安银行','time':day,'qccje':5e7,'qczf':5,'qcwtje':1e8}]))
        await save_evidence('stockpool_limit_up',day,ok([{'code':'000001','lbc':9}]))
        await save_evidence('stockpool_limit_up','2025-03-11',ok([{'code':'000001','lbc':2}]))
        pre=await build(day,'pre','short')
        assert pre['rows'][0]['price'] is None and pre['rows'][0]['consecutive']==2
        assert pre['context_date']=='2025-03-11'
        r=await build(day)
        assert r['total']==1 and r['rows'][0]['name']=='平安银行'
        assert r['rows'][0]['score']==85 and r['previous_date']=='2025-03-11'
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
            plan={'day':day,'code':'000001','mode':'short','phase':'live','note':'original'}
            assert (await c.post('/api/workbench/plans',json=plan)).json()['created']
            plan['note']='overwrite attempt'
            assert not (await c.post('/api/workbench/plans',json=plan)).json()['created']
            plans=(await c.get('/api/workbench/plans',params={'day':day})).json()['items']
            assert plans[0]['note']=='original' and plans[0]['reference_price']==10
            assert plans[0]['change_since_saved']==0
            bad=await c.post('/api/workbench/collect',json={'day':day,'stage':'history','codes':['../../secret']})
            assert bad.status_code==422
            # Failed refresh does not silently reuse the previous good sample.
            await save_evidence('market_snapshot_all',day,{'ok':False,'data':None,'msg':'失败'})
            assert (await build(day))['total']==0
            from app.services.workbench import local_fallback
            local=await local_fallback('stockpool_limit_up',day,{'ok':False})
            assert local['_local'] and local['ok']
            result=await save_evidence('stockpool_limit_up',day,local)
            assert result['status']=='local'
            rejected=await c.post('/api/workbench/collect',json={'day':day,'stage':'quote'})
            assert rejected.status_code==422
    finally:
        await engine.dispose()


async def test_workbench_recovers_interrupted_jobs():
    from app.services.workbench import recover_jobs
    try:
        async with engine.begin() as c:
            await c.execute(text("INSERT INTO wb_jobs(id,status,stage,trade_date,total) VALUES ('interrupted-test','running','live','2026-09-17',10)"))
        await recover_jobs()
        async with engine.connect() as c:
            row=(await c.execute(text("SELECT status,results,finished_at FROM wb_jobs WHERE id='interrupted-test'"))).first()
            assert row[0]=='failed' and row[1][-1]['status']=='error' and row[2] is not None
    finally:
        await engine.dispose()
