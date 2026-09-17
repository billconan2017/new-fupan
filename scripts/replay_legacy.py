"""Read-only old strategy study; run manually, no remote requests or broker orders."""
import sys,json,sqlite3,hashlib,os
from pathlib import Path
from collections import Counter
from datetime import datetime
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.services.legacy_rules.stage import _intraday_stage_status
from app.services.legacy_replay import feature,record_exclusion,price_paths
ROOT=Path(__file__).resolve().parents[1];BASE=Path(os.environ.get('LEGACY_ROOT','/home/bill/.hermes/workspace/LocalStockAllInOne'))
def connect(p):
 c=sqlite3.connect(p.resolve().as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row;c.execute('PRAGMA query_only=ON');return c

def main():
 dbs=[connect(BASE/'data'/n) for n in ('market_cache.db','market_cache_backup_19gb.db','market_cache_cold.db')]
 rows=[dict(r) for r in dbs[0].execute('SELECT trade_date,stock_code,stock_name,stage,status,selected_time,created_at,jjzf,raw_json,source FROM intraday_selection_result ORDER BY trade_date,rank_no')]
 calkey=hashlib.sha256(json.dumps(['basic_trade_calendar',{'year':'2026'}],sort_keys=True).encode()).hexdigest()
 calendar=json.loads((ROOT/'data/research/recent_evidence'/f'{calkey}.json').read_text())['data']
 sessions=sorted({d[:4]+'-'+d[4:6]+'-'+d[6:8] if len(d)==8 else d[:10] for d in calendar if isinstance(d,str) and len(d)>=8})
 if not sessions:raise ValueError('Missing verified local calendar')
 report={'complete':False,'generated_at':datetime.now().astimezone().isoformat(),'record_count':len(rows),'days':len({r['trade_date'] for r in rows}),'stages':dict(Counter(r['stage'] for r in rows)),'sources':dict(Counter(r['source'] for r in rows)), 'strict_record_audit':dict(Counter(record_exclusion(r) or '同日10点前记录（尚不证明成交）' for r in rows)), 'trades':[],'excluded':{},'rule_counts':{},'comparisons':[], 'note':'旧app.py承接/修复阶段规则的历史重建：种子池可能事后回填，非历史实时推荐业绩；未复现完整种子、板块联动及v2情绪引擎。用连续交易1分钟数据重建09:31/09:40特征，缺均价拒绝，下一分钟价格作参考；T+1/3/5收盘路径共用完整样本。未核验复权、涨跌停成交和手续费，不称收益或可执行胜率。'}
 seeds={}
 for r in rows:
  if r['stage']=='observe925':seeds.setdefault((r['trade_date'],r['stock_code']),r)
 misses=Counter();counts=Counter();coverage=Counter()
 for (day,code),r in seeds.items():
  full=code+('.SH' if code.startswith('6') else '.SZ')
  minute=[]
  for db in dbs[:2]:
   minute=[dict(x) for x in db.execute("SELECT time,price,avg,volume FROM stock_minute_kline WHERE code IN (?,?) AND trade_date=? AND period=1 AND time>='09:30' AND time<'10:00' ORDER BY time",(full,code,day))]
   if minute:break
  if not minute:misses['无09:30至10:00分钟历史']+=1;continue
  coverage['有早盘分钟的种子']+=1
  ix=sessions.index(day) if day in sessions else -1
  if ix<=0:misses['交易日历缺失']+=1;continue
  daily={}
  for db in reversed(dbs):
   for b in db.execute('SELECT * FROM stock_daily_kline WHERE code IN (?,?) AND trade_date>=? AND trade_date<=?',(full,code,sessions[ix-1],sessions[min(ix+5,len(sessions)-1)])):daily[b['trade_date']]=dict(b)
  prev=daily.get(sessions[ix-1])
  if not prev or not prev.get('close'):misses['前一交易日日线缺失']+=1;continue
  feats={t:feature(minute,t,prev['close']) for t in ('09:31','09:40')}
  inp={'code':code,'date':day,'prev_close':prev['close'],'jjzf':r['jjzf']}
  if r['jjzf'] is None:misses['竞价涨幅缺失']+=1;continue
  for stage,until,target in [('945','09:31','早确认池'),('1000','09:40','加仓确认池')]:
   if feats[until] is None:misses[until+'特征不足或均价缺失']+=1;continue
   reader=lambda code,date,until,prev_close=None:feats[until]
   status,_,_,_= _intraday_stage_status(inp,prev,stage,reader);counts[until+' '+status]+=1
   if status!=target:continue
   # Data used includes the labelled minute: entry reference strictly from next minute.
   next_time='09:32' if until=='09:31' else '09:41'
   entry=next((x['price'] for x in minute if str(x['time'])[:5]==next_time and x['price'] and x['price']>0),None)
   if not entry:misses['通过但下一分钟参考价缺失']+=1;continue
   paths=price_paths(entry,daily,sessions[ix+1:ix+6])
   if not paths:misses['通过但后续5交易日日线不完整/异常']+=1;continue
   report['trades'].append({'day':day,'code':code,'name':r['stock_name'],'stage':until,'entry_time':next_time,'entry_price':entry,'record_was_backfilled':not str(r['created_at']).startswith(day), 'seed_created_at':r['created_at'],'paths':paths})
 report.update(excluded=dict(misses),rule_counts=dict(counts),coverage=dict(coverage),seed_count=len(seeds))
 for stage in ['09:31','09:40']:
  cohort=[t for t in report['trades'] if t['stage']==stage]
  for h in (1,3,5):
   vals=[p['price_change_pct'] for t in cohort for p in t['paths'] if p['hold']==h]
   report['comparisons'].append({'stage':stage,'hold':h,'count':len(vals),'positive_rate':round(sum(v>0 for v in vals)/len(vals)*100,2) if vals else None,'mean_price_change':round(sum(vals)/len(vals),3) if vals else None})
 report['rule_sha256']=hashlib.sha256((ROOT/'backend/app/services/legacy_rules/stage.py').read_bytes()).hexdigest()
 report['sample_dates']=sorted({t['day'] for t in report['trades']})
 report['complete']=True;out=ROOT/'data/research/legacy_replay.json';out.parent.mkdir(parents=True,exist_ok=True);tmp=out.with_suffix('.tmp');tmp.write_text(json.dumps(report,ensure_ascii=False,indent=2));tmp.replace(out)
 print(json.dumps({k:v for k,v in report.items() if k not in ('trades','note')},ensure_ascii=False,indent=2))
 for db in dbs:db.close()
if __name__=='__main__':main()
