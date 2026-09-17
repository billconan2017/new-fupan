"""Prospective observations and fixed-rule simulations. No broker or order execution."""
import json
from datetime import datetime
from fastapi.encoders import jsonable_encoder
from sqlalchemy import text
from app.database import engine
from app.services import workbench as wb
from app.services.data_evidence import SH,quote_time
from app.services.research import preparation
from app.services.recent_replay import choose_candidates,evaluate,POLICY
from app.liangmai.parsing import records,source_date
STRATEGIES={'hot_auction_v1':'前日热点＋竞价','close_auction_v1':'前晚精选＋竞价'}
def encoded(v):return json.dumps(jsonable_encoder(v),ensure_ascii=False)
def close_picks(rows):
 out=[];groups={}
 for r in rows:
  if not r['code'].startswith(('00','60')) or r['overlap']<2 or (r['amount'] or 0)<1e8 or not (r['price'] or 0)>0:continue
  group=r['industry']
  if groups.get(group,0)>=2:continue
  out.append(r);groups[group]=groups.get(group,0)+1
  if len(out)==5:break
 return out
async def freeze(day,now=None):
 now=now or datetime.now(SH)
 if day!=now.date().isoformat():return {'state':'historical_not_frozen'}
 hm=now.strftime('%H:%M');phase='review' if hm>='17:10' else 'pre' if '09:26'<=hm<'09:30' else None
 if not phase:return {'state':'outside_signal_window'}
 async with engine.connect() as c:
  if (await c.execute(text('SELECT 1 FROM wb_paper_batches WHERE trade_date=:d AND phase=:p'),{'d':day,'p':phase})).scalar():return {'state':'already_frozen'}
 ev=await wb.evidence(day);signals=[]
 if phase=='review':
  prep=await preparation(day)
  if not prep['ready_for_decision']:return {'state':'closing_evidence_incomplete'}
  rows=close_picks(prep['rows'])
  payload={'rows':rows,'hot_codes':[r['code'] for r in prep['rows']],'window':prep['window'],'sources':prep['sources'],'rule':'close-overlap-v1'}
 else:
  e=ev.get('auction_morning_grab_amount',{});stamp=quote_time(e.get('fetched_at'))
  if e.get('status')!='ready' or not stamp or stamp.date()!=now.date() or stamp.strftime('%H:%M')<'09:26' or stamp>now:return {'state':'auction_evidence_incomplete'}
  cal=(ev.get('basic_trade_calendar',{}).get('payload') or [])+(ev.get('calendar_previous_year',{}).get('payload') or [])
  previous=max((source_date(d) for d in cal if source_date(d) and source_date(d)<day),default=None)
  async with engine.connect() as c:
   prior=(await c.execute(text("SELECT payload,created_at FROM wb_paper_batches WHERE trade_date=:d AND phase='review'"),{'d':previous})).first()
  if not prior or prior.created_at.astimezone(SH).date().isoformat()!=previous:return {'state':'no_frozen_previous_close'}
  prior=prior.payload
  for strategy,hot in [('hot_auction_v1',set(prior['hot_codes'])),('close_auction_v1',{r['code'] for r in prior['rows']})]:
   for r in choose_candidates(records(e['payload']),day,hot):
    signals.append({'strategy':strategy,'row':r,'policy':POLICY,'previous_date':previous,'auction_fetched_at':stamp.isoformat(),'origin':'prospective'})
  payload={'signals':signals,'previous_date':previous,'rule':'paper-observer-v1'}
 async with engine.begin() as c:
  created=(await c.execute(text('INSERT INTO wb_paper_batches(trade_date,phase,payload) VALUES(:d,:p,CAST(:v AS JSONB)) ON CONFLICT DO NOTHING RETURNING trade_date'),{'d':day,'p':phase,'v':encoded(payload)})).scalar()
  if not created:return {'state':'already_frozen'}
  for s in signals:
   r=s['row']
   await c.execute(text('INSERT INTO wb_paper_signals(trade_date,strategy,code,name,evidence) VALUES(:d,:s,:c,:n,CAST(:e AS JSONB)) ON CONFLICT DO NOTHING'),{'d':day,'s':s['strategy'],'c':r['code'],'n':r['name'],'e':encoded(s)})
  for r in payload.get('rows',[]) if phase=='review' else [s['row'] for s in signals]:
   frozen={'row':r,'rule_version':'paper-observer-v1','origin':'prospective','window':payload.get('window'),'automatic':True}
   await c.execute(text("INSERT INTO wb_plans(trade_date,code,name,mode,phase,note,evidence) VALUES(:d,:c,:n,'short',:p,:note,CAST(:e AS JSONB)) ON CONFLICT DO NOTHING"),{'d':day,'c':r['code'],'n':r['name'],'p':phase,'note':'自动冻结观察，不代表成交；两组策略分开统计','e':encoded(frozen)})
 return {'state':'frozen','phase':phase,'count':len(signals) if phase=='pre' else len(payload['rows'])}
async def evaluate_saved(day):
 ev=await wb.evidence(day);cal=(ev.get('basic_trade_calendar',{}).get('payload') or [])+(ev.get('calendar_previous_year',{}).get('payload') or [])
 dates=sorted({source_date(x) for x in cal if source_date(x) and source_date(x)<=day})
 if not dates:return {'state':'calendar_missing'}
 async with engine.connect() as c:
  rows=(await c.execute(text('SELECT * FROM wb_paper_signals WHERE trade_date>=:start AND trade_date<=:d ORDER BY trade_date,id'),{'start':dates[-10] if len(dates)>=10 else dates[0],'d':day})).mappings().all()
 cache={};count=0
 for row in rows:
  signal=row['trade_date'];code=row['code'];key=(signal,code)
  if key not in cache:
   compact=signal.replace('-','');end=day.replace('-','')
   calls=[('minute','kline_history',{'full_code':code,'interval':'5','cq':'n','st':compact+'093000','et':compact+'100000','lt':20}),('daily','kline_history',{'full_code':code,'interval':'d','cq':'n','st':compact,'et':end,'lt':20}),('limits','kline_stop_price_history',{'full_code':code,'st':compact,'et':end,'lt':20})]
   data={}
   for label,api,params in calls:
    response=await wb.liangmai.call(api,params,ttl=300)
    await wb.save_evidence(f'paper_{label}:{signal}:{code}',day,response)
    data[label]=records(response.get('data')) if response.get('ok') else []
   cache[key]=data
  data=cache[key];result=evaluate(row['evidence']['row'],cal,data['minute'],data['daily'],data['limits'],day,policy=row['evidence']['policy'])
  async with engine.begin() as c:
   await c.execute(text('UPDATE wb_paper_signals SET result=CAST(:r AS JSONB),evaluated_at=now() WHERE id=:id'),{'r':encoded(result),'id':row['id']})
  count+=1
 return {'state':'evaluated','signals':count}
async def run(day):
 frozen=await freeze(day);now=datetime.now(SH)
 evaluated=await evaluate_saved(day) if now.strftime('%H:%M')>='15:45' else {'state':'await_close'}
 return {'api':'paper_observer','status':'ready','rows':frozen.get('count',0),'freeze':frozen,'evaluation':evaluated}
def summaries(rows):
 out=[]
 for strategy,name in STRATEGIES.items():
  signals=[r for r in rows if r['strategy']==strategy]
  for hold in POLICY['holds']:
   paths=[p for r in signals for p in (r.get('result') or {}).get('paths',[]) if p['hold']==hold];done=[p for p in paths if p['status']=='evaluated'];n=len(done)
   common=[r for r in signals if len((r.get('result') or {}).get('paths',[]))==3 and all(p['status']=='evaluated' for p in r['result']['paths'])]
   common_values=[p['net_pct'] for r in common for p in r['result']['paths'] if p['hold']==hold]
   out.append({'strategy':strategy,'name':name,'hold':hold,'common_count':len(common),'common_mean':round(sum(common_values)/len(common_values),3) if common_values else None,'signals':len(signals),'evaluated':n,'pending':sum(p['status']=='pending' for p in paths),'unknown':sum(p['status'] in ('unknown','blocked') for p in paths),'unresolved_entries':sum((r.get('result') or {}).get('entry_status') not in ('simulated','not_entered') for r in signals),'not_entered':sum((r.get('result') or {}).get('entry_status')=='not_entered' for r in signals),'win_rate':round(sum(p['pnl']>0 for p in done)/n*100,1) if n else None,'mean_net_pct':round(sum(p['net_pct'] for p in done)/n,3) if n else None})
 return out
async def report():
 async with engine.connect() as c:
  rows=[dict(r) for r in (await c.execute(text('SELECT * FROM wb_paper_signals ORDER BY trade_date DESC,id DESC LIMIT 300'))).mappings()]
  batches=[dict(r) for r in (await c.execute(text('SELECT * FROM wb_paper_batches ORDER BY trade_date DESC,phase LIMIT 20'))).mappings()]
 return {'batches':batches,'signals':rows,'summary':summaries(rows),'policy':POLICY,'note':'只统计自动冻结后的模拟样本；两策略可含相同股票。盈利比例=扣费后盈利笔数/可评估退出笔数；缺数据和未到期单列。最近300条记录，非账户收益。'}
