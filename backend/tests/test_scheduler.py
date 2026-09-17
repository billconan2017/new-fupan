from unittest.mock import AsyncMock
import pytest
from app.services.trading_scheduler import TradingScheduler


async def test_backfill_passes_each_date(monkeypatch):
    s=TradingScheduler()
    s._async_post_market=AsyncMock(return_value={'pool':{'ok':True}})
    monkeypatch.setattr('app.services.trading_scheduler.is_trading_day',lambda d: d.weekday()<5)
    monkeypatch.setattr('app.services.trading_scheduler.asyncio.sleep',AsyncMock())
    r=await s.backfill('2026-09-14','2026-09-16')
    assert r['ok']
    assert [c.args[0] for c in s._async_post_market.call_args_list]==['2026-09-14','2026-09-15','2026-09-16']


async def test_manual_failure_is_not_reported_success():
    s=TradingScheduler()
    s._async_post_market=AsyncMock(return_value={'pool':{'ok':False}})
    r=await s.trigger_post_market('2026-09-14')
    assert not r['ok']
    s._async_post_market.assert_awaited_once_with('2026-09-14')


async def test_failed_jobs_remain_retryable(monkeypatch):
    s=TradingScheduler()
    worker=AsyncMock(return_value={'a':{'ok':False}})
    monkeypatch.setattr('app.services.trading_scheduler.asyncio.sleep',AsyncMock())
    await s._safe_execute('job','2026-09-16',worker)
    assert await s._check_idempotent('job','2026-09-16')
    assert 'job' in s._errors
    worker.return_value={'a':{'ok':True}}
    await s._safe_execute('job','2026-09-16',worker)
    assert not await s._check_idempotent('job','2026-09-16')
    assert 'job' not in s._errors


async def test_fetch_all_passes_date_to_all_workers():
    s=TradingScheduler()
    for name in ('_async_pre_market','_async_auction','_async_intraday','_async_post_market'):
        setattr(s,name,AsyncMock(return_value={'ok':True}))
    r=await s.trigger_fetch_all('2026-09-14')
    assert r['ok']
    s._async_auction.assert_awaited_once_with('2026-09-14')
    s._async_intraday.assert_awaited_once_with('手动','2026-09-14')
    s._async_post_market.assert_awaited_once_with('2026-09-14')
