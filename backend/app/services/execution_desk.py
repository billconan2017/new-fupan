"""Time-bounded paper confirmations. Never sends brokerage orders."""
import json
from datetime import datetime
from sqlalchemy import text
from fastapi.encoders import jsonable_encoder
from app.database import engine
from app.services.data_evidence import SH
from app.services import workbench as wb
from app.services.recent_replay import confirmation_gate,evaluate,POLICY
from app.liangmai.parsing import records

PRIMARY='close_auction_v1'

def phase_at(day,now):
 if day!=now.date().isoformat():return 'history'
 hm=now.strftime('%H:%M')
 if hm<'09:26':return 'prepare'
 if hm<'09:30':return 'auction'
 if hm<'09:35':return 'wait_bar'
 if hm<'09:40':return 'confirm'
 if hm<'09:45':return 'wait_entry'
 if hm<'10:00':return 'tracking'
 if hm<'15:00':return 'manage'
 return 'review'

def event_decision(day,now,minute,gate=None,calendar=None,limits=None,candidate=None):
 """Live events can only be frozen in their actual observation windows."""
 if day!=now.date().isoformat():return None
 hm=now.strftime('%H:%M')
 if gate is None:
  if '09:35'<=hm<'09:40':
   decision=confirmation_gate(day,minute)
   return ('gate',decision) if decision['state']!='unknown' else None
  if hm>='09:40':return ('gate',{'state':'missed','reason':'未在09:40前取得有效确认，禁止盘后补造实时入选'})
  return None
 if gate.get('state')!='confirmed' or hm<'09:45':return None
 if hm>='10:00':return ('entry',{'state':'missed','reason':'未在10点前核验模拟入场'})
 result=evaluate(candidate,calendar or [],minute,[],limits or [],day,policy=POLICY)
 if result['entry_status']=='unknown':return None
 return ('entry',{'state':result['entry_status'],'reason':result['reason'],'result':result})

async def run(day,now=None):
 now=now or datetime.now(SH)
 if day!=now.date().isoformat() or not '09:35'<=now.strftime('%H:%M')<='10:00':
  return {'api':'paper_live','status':'ready','rows':0,'state':'outside_window'}
 async with engine.connect() as c:
  signals=[dict(r) for r in (await c.execute(text('SELECT * FROM wb_paper_signals WHERE trade_date=:d ORDER BY id'),{'d':day})).mappings()]
  saved=[dict(r) for r in (await c.execute(text('SELECT e.* FROM wb_paper_events e JOIN wb_paper_signals s ON s.id=e.signal_id WHERE s.trade_date=:d'),{'d':day})).mappings()]
 existing={(r['signal_id'],r['kind']):r for r in saved};packets={};written=0
 ev=await wb.evidence(day);calendar=ev.get('basic_trade_calendar',{}).get('payload') or []
 for s in signals:
  if s['created_at'].astimezone(SH).date().isoformat()!=day or s['created_at'].astimezone(SH).strftime('%H:%M')>='09:30':continue
  gate=existing.get((s['id'],'gate'))
  if (s['id'],'entry') in existing or gate and gate['payload'].get('state')!='confirmed':continue
  # A tampered/late gate cannot authorize an earlier simulated entry.
  if gate and gate['created_at'].astimezone(SH).strftime('%H:%M')>='09:40':continue
  code=s['code']
  if code not in packets:
   compact=day.replace('-','');r=await wb.liangmai.call('kline_history',{'full_code':code,'interval':'5','cq':'n','st':compact+'093000','et':now.strftime('%Y%m%d%H%M%S'),'lt':20},ttl=30)
   await wb.save_evidence('paper_live_minute:'+code,day,r)
   minute=records(r.get('data')) if r.get('ok') else [];limits=[]
   if now.strftime('%H:%M')>='09:45':
    r=await wb.liangmai.call('kline_stop_price_history',{'full_code':code,'st':compact,'et':compact,'lt':5},ttl=300)
    await wb.save_evidence('paper_live_limits:'+code,day,r)
    limits=records(r.get('data')) if r.get('ok') else []
   packets[code]=(minute,limits)
  minute,limits=packets[code]
  observed=max(now,datetime.now(SH))
  decision=event_decision(day,observed,minute,gate['payload'] if gate else None,calendar,limits,s['evidence']['row'])
  if decision:
   kind,payload=decision;payload.update(observed_at=observed.isoformat(),policy_version=POLICY['version'],minute_evidence=minute,limits_evidence=limits)
   async with engine.begin() as c:
    made=(await c.execute(text('INSERT INTO wb_paper_events(signal_id,kind,payload,created_at) VALUES(:id,:kind,CAST(:p AS JSONB),:now) ON CONFLICT DO NOTHING RETURNING id'),{'id':s['id'],'kind':kind,'p':json.dumps(jsonable_encoder(payload),ensure_ascii=False),'now':observed})).scalar()
    written+=bool(made)
 return {'api':'paper_live','status':'ready','rows':written,'state':'observed','signals':len(signals)}

async def report(day):
 async with engine.connect() as c:
  signals=[dict(r) for r in (await c.execute(text('SELECT * FROM wb_paper_signals WHERE trade_date=:d ORDER BY strategy,id'),{'d':day})).mappings()]
  events=[dict(r) for r in (await c.execute(text('SELECT e.* FROM wb_paper_events e JOIN wb_paper_signals s ON s.id=e.signal_id WHERE s.trade_date=:d'),{'d':day})).mappings()]
  close=(await c.execute(text("SELECT trade_date,payload,created_at FROM wb_paper_batches WHERE phase='review' AND trade_date<=:d ORDER BY trade_date DESC LIMIT 1"),{'d':day})).mappings().first()
 mapping={(e['signal_id'],e['kind']):e for e in events}
 items=[]
 for s in signals:
  gate=mapping.get((s['id'],'gate'));entry=mapping.get((s['id'],'entry'))
  state=(entry or gate or {}).get('payload',{}).get('state','waiting')
  items.append({'id':s['id'],'code':s['code'],'name':s['name'],'strategy':s['strategy'],'score':s['evidence']['row'].get('score'),'auction_pct':s['evidence']['row'].get('auction_pct'),'state':state,'reason':(entry or gate or {}).get('payload',{}).get('reason','等待09:35首根5分钟K线确认'),'observed_at':(entry or gate or {}).get('created_at'),'entry':entry['payload'].get('result') if entry else None,'result':s['result']})
 evaluated=[p for r in items if r['strategy']==PRIMARY and r['state']=='simulated' and (r['result'] or {}).get('execution_origin')=='prospective_confirmed' for p in r['result'].get('paths',[]) if p['hold']==1 and p['status']=='evaluated']
 stats={'count':len(evaluated),'win_rate':round(sum(p['pnl']>0 for p in evaluated)/len(evaluated)*100,1) if evaluated else None,'mean_net_pct':round(sum(p['net_pct'] for p in evaluated)/len(evaluated),3) if evaluated else None}
 return {'stats':stats,'day':day,'phase':phase_at(day,datetime.now(SH)),'primary':PRIMARY,'policy':POLICY,'items':items,'last_close':dict(close) if close else None,'counts':{state:sum(r['state']==state for r in items if r['strategy']==PRIMARY) for state in ('waiting','confirmed','simulated','rejected','missed','not_entered')},'note':'模拟执行；实时确认留痕与盘后重建分开。缺数据不买、错过不补；固定T+1/2/3比较，尚未证明持续盈利。'}
