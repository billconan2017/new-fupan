from datetime import datetime
from zoneinfo import ZoneInfo
from app.services.autocollect import slots

def at(s):return datetime.fromisoformat(s).replace(tzinfo=ZoneInfo('Asia/Shanghai'))

def test_no_lunch_weekend_or_late_auction():
    assert slots(at('2026-09-19T09:26:00'))==[]
    assert slots(at('2026-09-17T12:00:00'))==[]
    assert slots(at('2026-09-17T09:24:00'))==[]
    assert slots(at('2026-09-17T09:26:00'))==[('09:26','pre')]
    assert all(stage!='pre' for _,stage in slots(at('2026-09-17T09:31:00')))

def test_coalesce_intervals_and_latest_close_slot():
    assert slots(at('2026-09-17T09:34:59'))==[('09:30','live'),('09:30','intraday')]
    assert slots(at('2026-09-17T15:20:00'))==[]
    assert slots(at('2026-09-17T19:00:00'))==[('17:30',s) for s in ('review','intraday','history')]
    assert slots(at('2026-09-17T23:59:00'))==[('22:00',s) for s in ('review','intraday','history')]

import os
import pytest
from sqlalchemy import text
from app.services import autocollect as ac
from app.database import engine

@pytest.mark.skipif(os.environ.get('FUPAN_TEST_DB')!='1',reason='disposable database only')
async def test_calendar_gate_and_durable_duplicate_prevention(monkeypatch):
    async def ev(day):return {'basic_trade_calendar':{'status':'ready','payload':['2026-09-18']}}
    monkeypatch.setattr(ac.wb,'evidence',ev)
    calls=[]
    async def start(day,stage,codes):
        calls.append(stage)
        async with engine.begin() as c:
            await c.execute(text("INSERT INTO wb_jobs(id,status,stage,trade_date,total) VALUES('timer-test','done',:s,:d,0)"),{'s':stage,'d':day})
        return {'ok':True,'job_id':'timer-test'}
    monkeypatch.setattr(ac.wb,'start_job',start)
    try:
        assert (await ac.tick(at('2026-09-17T09:26:00')))['state']=='closed'
        assert not calls
        assert (await ac.tick(at('2026-09-18T09:26:00')))['state']=='started'
        assert (await ac.tick(at('2026-09-18T09:27:00')))['state']=='already_run'
        assert calls==['pre']
    finally:
        await engine.dispose()

@pytest.mark.skipif(os.environ.get('FUPAN_TEST_DB')!='1',reason='disposable database only')
async def test_evidence_history_preserves_previous_snapshot():
    try:
        await ac.wb.save_evidence('archive-test','2026-09-01',{'ok':True,'data':[{'p':10}]})
        await ac.wb.save_evidence('archive-test','2026-09-01',{'ok':True,'data':[{'p':11}]})
        async with engine.connect() as c:
            rows=(await c.execute(text("SELECT payload FROM wb_evidence_history WHERE api='archive-test' ORDER BY id"))).scalars().all()
            assert [r[0]['p'] for r in rows]==[10,11]
        assert (await ac.wb.evidence('2026-09-01'))['archive-test']['payload'][0]['p']==11
    finally:
        await engine.dispose()
