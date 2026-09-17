from datetime import datetime
from zoneinfo import ZoneInfo
from app.services.execution_desk import event_decision,phase_at
from app.services.recent_replay import confirmation_gate
from app.services.autocollect import slots

def at(hm,day='2026-09-18'):return datetime.fromisoformat(day+'T'+hm).replace(tzinfo=ZoneInfo('Asia/Shanghai'))
def bars():return [{'t':'2026-09-18 09:35:00','o':10,'h':10.3,'l':9.99,'c':10.2,'sf':0,'v':100}, {'t':'2026-09-18 09:45:00','o':10.2,'h':10.4,'l':10.1,'c':10.3,'sf':0,'v':100}]

def test_live_gate_same_as_replay_and_cannot_backfill():
 d='2026-09-18';b=bars()
 assert event_decision(d,at('09:35:01'),b)==('gate',confirmation_gate(d,b))
 assert event_decision(d,at('09:34:59'),b) is None
 assert event_decision(d,at('09:40:00'),b)[1]['state']=='missed'
 assert event_decision(d,at('09:35:00','2026-09-21'),b) is None

def test_unknown_retries_and_negative_is_immutable_rejection():
 assert event_decision('2026-09-18',at('09:36:00'),[]) is None
 b=bars();b[0]['c']=10
 g=event_decision('2026-09-18',at('09:36:00'),b)[1]
 assert g['state']=='rejected'
 assert event_decision('2026-09-18',at('09:46:00'),bars(),g) is None

def test_simulated_entry_waits_completed_bar_and_valid_limits():
 d='2026-09-18';g={'state':'confirmed'};cal=[d,'2026-09-21'];limits=[{'t':d,'h':11,'l':9}];candidate={'signal_date':d,'code':'000001'}
 assert event_decision(d,at('09:44:59'),bars(),g,cal,limits,candidate) is None
 assert event_decision(d,at('09:45:05'),bars(),g,cal,[],candidate) is None
 kind,p=event_decision(d,at('09:45:05'),bars(),g,cal,limits,candidate)
 assert kind=='entry' and p['state']=='simulated'
 assert p['result']['paths'][0]['exit_date']=='2026-09-21'
 assert event_decision(d,at('10:00:00'),bars(),g,cal,limits,candidate)[1]['state']=='missed'

def test_timer_prioritizes_gate_and_leaves_even_minutes_for_quotes():
 assert slots(at('09:35:00'))[0][1]=='paper_live'
 assert slots(at('09:37:00'))[0][1]=='paper_live'
 assert slots(at('09:36:00'))[0][1]=='live'
 assert phase_at('2026-09-18',at('09:39:00'))=='confirm'

import os,json,pytest
from unittest.mock import AsyncMock
from sqlalchemy import text
from app.database import engine
from app.services import execution_desk as desk

@pytest.mark.skipif(os.environ.get('FUPAN_TEST_DB')!='1',reason='disposable database only')
async def test_live_events_are_immutable_and_entries_need_real_gate(monkeypatch):
 class Clock:
  value=at('09:36:00')
  @classmethod
  def now(cls,tz):return cls.value
 monkeypatch.setattr(desk,'datetime',Clock)
 monkeypatch.setattr(desk.wb,'evidence',AsyncMock(return_value={'basic_trade_calendar':{'payload':['2026-09-18','2026-09-21']}}))
 monkeypatch.setattr(desk.wb,'save_evidence',AsyncMock())
 async def call(api,params,**kw):
  return {'ok':True,'data':bars() if api=='kline_history' else [{'t':'2026-09-18','h':11,'l':9}]}
 monkeypatch.setattr(desk.wb.liangmai,'call',call)
 try:
  async with engine.begin() as c:
   sid=(await c.execute(text("INSERT INTO wb_paper_signals(trade_date,strategy,code,name,evidence,created_at) VALUES('2026-09-18','test_primary','600000','测试',CAST(:e AS JSONB),'2026-09-18T09:27:00+08:00') RETURNING id"),{'e':json.dumps({'row':{'signal_date':'2026-09-18','code':'600000'}})})).scalar()
  assert (await desk.run('2026-09-18',Clock.value))['rows']>=1
  async with engine.connect() as c:
   first=(await c.execute(text("SELECT payload FROM wb_paper_events WHERE signal_id=:id AND kind='gate'"),{'id':sid})).scalar()
  assert first['state']=='confirmed'
  Clock.value=at('09:46:00');await desk.run('2026-09-18',Clock.value)
  Clock.value=at('09:48:00');await desk.run('2026-09-18',Clock.value)
  async with engine.connect() as c:
   rows=(await c.execute(text('SELECT kind,payload FROM wb_paper_events WHERE signal_id=:id'),{'id':sid})).all()
  assert len(rows)==2 and dict(rows)['gate']==first
  assert dict(rows)['entry']['state']=='simulated'
 finally:
  async with engine.begin() as c:
   await c.execute(text('DELETE FROM wb_paper_events WHERE signal_id=:id'),{'id':sid})
   await c.execute(text('DELETE FROM wb_paper_signals WHERE id=:id'),{'id':sid})
  await engine.dispose()
