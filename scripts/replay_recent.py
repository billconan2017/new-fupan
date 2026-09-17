"""Reconstruct last five completed sessions. Cached raw evidence stays in ignored data/."""
import asyncio,json,sys,hashlib
from pathlib import Path
from datetime import datetime
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.services.recent_replay import POLICY,choose_candidates,evaluate
from app.services.workbench import code_of
from app.services.data_evidence import SH
from app.liangmai.client import LiangmaiClient
from app.config import get_settings
from app.liangmai.parsing import records,source_date,dragon_records
ROOT=Path(__file__).resolve().parents[1]/'data/research';CACHE=ROOT/'recent_evidence';OUT=ROOT/'recent_replay.json'
async def main():
 ROOT.mkdir(parents=True,exist_ok=True);CACHE.mkdir(exist_ok=True)
 client=LiangmaiClient(get_settings().model_copy(update={'liangmai_max_attempts':1,'liangmai_safe_rate':45}));await client.connect()
 report={'generated_at':datetime.now(SH).isoformat(),'policy':POLICY,'days':[],'trades':[],'calls':[],'complete':False,
 'note':'事后重建的固定规则模拟，非历史已发推荐、非真实成交。前日热点池部分响应不含日期，依赖服务端日期过滤。五分钟K线按结束时间解释，09:35确认后用09:45结束K线的开盘价模拟09:40入场。每笔独立1万元；佣金万三最低5元、双向过户费万分之0.1、卖出印花税万分之5、双向滑点各0.1%。重叠持仓未组成资金组合，平均单笔收益不是账户收益。'}
 def save():
  tmp=OUT.with_suffix('.tmp');tmp.write_text(json.dumps(report,ensure_ascii=False,indent=2));tmp.replace(OUT)
 async def call(api,params):
  digest=hashlib.sha256(json.dumps([api,params],sort_keys=True).encode()).hexdigest();path=CACHE/(digest+'.json')
  if path.exists():r=json.loads(path.read_text())
  else:
   r=await client.call(api,params)
   if r.get('ok'):path.write_text(json.dumps(r,ensure_ascii=False))
  report['calls'].append({'api':api,'params':params,'ok':r.get('ok'),'code':r.get('code'),'cache_file':path.name});save()
  print(api,params,r.get('ok'),flush=True);return r.get('data') if r.get('ok') else None
 try:
  today=datetime.now(SH).date().isoformat();cal=await call('basic_trade_calendar',{'year':today[:4]}) or []
  sessions=sorted({d for x in cal if (d:=source_date(x)) and d<today});days=sessions[-5:];asof=sessions[-1];report.update(asof=asof,dates=days)
  for day in days:
   prev=sessions[sessions.index(day)-1];hot=set();sources=[]
   for api in ('stockpool_limit_up','stockpool_strong','lhb_daily'):
    data=await call(api,{'date' if api=='lhb_daily' else 'trade_date':prev});rs=dragon_records(data) if api=='lhb_daily' else records(data)
    dates={source_date(r.get('endDate') or r.get('time') or r.get('trade_date')) for r in rs}-{None}
    mismatch=bool(dates and dates!={prev})
    if not mismatch:hot.update(code_of(r) for r in rs if code_of(r))
    sources.append({'api':api,'date':prev,'count':len(rs),'status':'error' if data is None else 'mismatch' if mismatch else 'dated' if dates=={prev} else 'date_parameter_only'})
   auction=records(await call('auction_morning_grab_amount',{'tradeDate':day,'period':'0','type':'1'}))
   picks=choose_candidates(auction,day,hot)
   if any(s['status'] in ('error','mismatch') for s in sources):picks=[]
   report['days'].append({'date':day,'previous_date':prev,'sources':sources,'auction_rows':len(auction),'picked':len(picks),'codes':[r['code'] for r in picks]});save()
   for row in picks:
    code=row['code'];compact=day.replace('-','');end=asof.replace('-','')
    minute=records(await call('kline_history',{'full_code':code,'interval':'5','cq':'n','st':compact+'093000','et':compact+'100000','lt':20}))
    daily=records(await call('kline_history',{'full_code':code,'interval':'d','cq':'n','st':compact,'et':end,'lt':30}))
    limits=records(await call('kline_stop_price_history',{'full_code':code,'st':compact,'et':end,'lt':30}))
    result=evaluate(row,cal,minute,daily,limits,asof);report['trades'].append(result);save()
  summaries=[]
  for hold in POLICY['holds']:
   paths=[p for t in report['trades'] for p in t['paths'] if p['hold']==hold];values=[p for p in paths if p['status']=='evaluated']
   summaries.append({'hold':hold,'counts':dict(Counter(p['status'] for p in paths)),'count':len(values),'mean_net_pct':round(sum(p['net_pct'] for p in values)/len(values),3) if values else None,'win_rate':round(sum(p['pnl']>0 for p in values)/len(values)*100,1) if values else None,'sample_pnl_sum':round(sum(p['pnl'] for p in values),2) if values else None})
  # Separate common cohort prevents choosing a horizon simply because more recent dates lack exits.
  common=[t for t in report['trades'] if len(t['paths'])==3 and all(p['status']=='evaluated' for p in t['paths'])]
  report['common_cohort']={'count':len(common),'means':{str(h):round(sum(next(p['net_pct'] for p in t['paths'] if p['hold']==h) for t in common)/len(common),3) if common else None for h in POLICY['holds']}}
  report.update(complete=True,summary=summaries,entry_counts=dict(Counter(t['entry_status'] for t in report['trades'])));save()
 finally:await client.close()
if __name__=='__main__':asyncio.run(main())
