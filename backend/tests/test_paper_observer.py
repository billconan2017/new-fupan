import os
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import AsyncMock
import pytest
from sqlalchemy import text
from app.database import engine
from app.services import paper_observer as p

def at(t):return datetime.fromisoformat(t).replace(tzinfo=ZoneInfo('Asia/Shanghai'))

def test_statistics_do_not_count_pending_or_missing_as_wins_or_losses():
 rows=[{'strategy':'hot_auction_v1','result':{'entry_status':'simulated','paths':[{'hold':1,'status':'evaluated','pnl':-10,'net_pct':-1},{'hold':2,'status':'pending'}]}},{'strategy':'hot_auction_v1','result':{'entry_status':'unknown','paths':[]}}]
 s=p.summaries(rows)
 assert s[0]['win_rate']==0 and s[0]['evaluated']==1 and s[0]['signals']==2
 assert s[0]['unresolved_entries']==1 and s[1]['win_rate'] is None and s[1]['pending']==1

async def test_late_and_historical_signals_are_never_backfilled():
 assert (await p.freeze('2026-09-17',at('2026-09-18T09:27:00')))['state']=='historical_not_frozen'
 assert (await p.freeze('2026-09-18',at('2026-09-18T09:31:00')))['state']=='outside_signal_window'

@pytest.mark.skipif(os.environ.get('FUPAN_TEST_DB')!='1',reason='disposable database only')
async def test_close_to_auction_freeze_is_immutable_and_deduplicated(monkeypatch):
 row={'code':'000001','name':'测试','industry':'银行','overlap':2,'amount':2e8,'price':10}
 prep={'ready_for_decision':True,'rows':[row],'window':{'buy_date':'2026-09-18','earliest_sell_date':'2026-09-21'},'sources':[]}
 monkeypatch.setattr(p,'preparation',AsyncMock(return_value=prep))
 ev={'basic_trade_calendar':{'payload':['2026-09-17','2026-09-18','2026-09-21']},'auction_morning_grab_amount':{'status':'ready','fetched_at':at('2026-09-18T09:26:30'),'payload':[{'code':'000001','name':'测试','time':'2026-09-18','qczf':5,'qccje':5e7,'qcwtje':1e8}]}}
 monkeypatch.setattr(p.wb,'evidence',AsyncMock(return_value=ev))
 try:
  assert (await p.freeze('2026-09-17',at('2026-09-17T17:31:00')))['count']==1
  assert (await p.freeze('2026-09-17',at('2026-09-17T20:31:00')))['state']=='already_frozen'
  async with engine.begin() as c:
   await c.execute(text("UPDATE wb_paper_batches SET created_at='2026-09-17T17:31:00+08:00' WHERE trade_date='2026-09-17'"))
  assert (await p.freeze('2026-09-18',at('2026-09-18T09:27:00')))['count']==2
  assert (await p.freeze('2026-09-18',at('2026-09-18T09:28:00')))['state']=='already_frozen'
  async with engine.connect() as c:
   assert (await c.execute(text('SELECT count(*) FROM wb_paper_signals'))).scalar()==2
   assert (await c.execute(text("SELECT count(*) FROM wb_plans WHERE trade_date='2026-09-18' AND code='000001' AND phase='pre'"))).scalar()==1
 finally:await engine.dispose()

async def test_daily_display_does_not_show_future_or_unclosed_day(monkeypatch):
 from app.routers.workbench import history
 from datetime import date
 monkeypatch.setattr(p.wb,'evidence',AsyncMock(return_value={'kline_history:000001':{'status':'ready','payload':[{'t':'2026-09-16','c':10},{'t':'2026-09-17','c':20},{'t':'2026-09-18','c':30}]}}))
 r=await history('000001',date(2026,9,17))
 assert r['items']==[{'t':'2026-09-16','c':10}]
