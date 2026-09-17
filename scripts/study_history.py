"""Small reproducible historical coverage + fixed-rule price-path study. No orders."""
import asyncio,json,sys
from pathlib import Path
from collections import Counter
from datetime import datetime
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.liangmai.client import LiangmaiClient
from app.config import get_settings
from app.liangmai.parsing import records,source_date,number
from app.services.holding_study import evaluate_path,HOLDS
DAYS=['2026-06-16','2026-07-16','2026-08-17','2026-08-24','2026-08-31','2026-09-01']
OUT=Path('data/research/history_study.json')
async def main():
 c=LiangmaiClient(get_settings().model_copy(update={'liangmai_max_attempts':1,'liangmai_safe_rate':45}));await c.connect()
 report={'generated_at':datetime.now().astimezone().isoformat(),'coverage':[],'trades':[],'comparisons':[],
  'note':'固定6个历史日期、当日强势池中普通沪深主板成交额前5名的探索性价格路径研究。不是原短线策略回测或历史推荐业绩，不使用当前赢家回填。所有持有期使用同一批完整样本；不含手续费与滑点，也未证明开盘/收盘价可成交，因此不能据此给出“赚多少钱”或最佳持有期。规则未经过独立前瞻检验。',
  'rule':{'version':'strong-pool-path-v1','dates':DAYS,'universe':'历史当日强势池，代码00/60，排除当日ST/退名称，成交额降序前5','entry':'次一交易日开盘参考价','exit':'买入后的第1/2/3/5/10个交易日收盘参考价','same_cohort':True,'fees_included':False,'execution_verified':False}}
 def save():
  OUT.parent.mkdir(parents=True,exist_ok=True);tmp=OUT.with_suffix('.tmp');tmp.write_text(json.dumps(report,ensure_ascii=False,indent=2));tmp.replace(OUT)
 async def call(api,params,day):
  r=await c.call(api,params);rs=records(r.get('data'));ds=sorted({d for b in rs for k in ('t','time','trade_date','date') if (d:=source_date(b.get(k)))})
  status=('ready' if r.get('data') else 'empty') if r.get('ok') else 'error'
  check=('匹配请求日期' if ds==[day] else '返回范围 '+ds[0]+' ~ '+ds[-1]) if ds else '响应未含可核验日期，不能证明历史日期正确'
  report['coverage'].append({'day':day,'api':api,'status':status,'rows':len(rs),'date_check':check});save()
  print(day,api,status,len(rs),flush=True);return r,rs,ds
 cal=(await c.call('basic_trade_calendar',{'year':'2026'})).get('data') or []
 for day in DAYS:
  _,pool,dates=await call('stockpool_strong',{'trade_date':day},day)
  # Pool APIs may lack row timestamps: retain the qualification explicitly in every sample.
  ranked=sorted([r for r in pool if str(r.get('dm','')).startswith(('00','60')) and 'ST' not in str(r.get('mc','')).upper() and '退' not in str(r.get('mc','')) and number(r.get('cje')) is not None],key=lambda r:-number(r['cje']))[:5]
  if dates and dates!=[day]:ranked=[]
  for api,params in [('lhb_daily',{'date':day}),('auction_morning_grab_amount',{'tradeDate':day,'period':'0','type':'1'})]:await call(api,params,day)
  for row in ranked:
   code=str(row['dm']).split('.')[0]
   r,bars,_=await call('kline_history',{'full_code':code,'interval':'d','cq':'n','st':day.replace('-',''),'et':'20260916','lt':120},day)
   result=evaluate_path(day,cal,bars) if r.get('ok') else {'status':'excluded','reason':'日线接口失败'}
   report['trades'].append({'signal_date':day,'code':code,'name':row.get('mc'),'historical_date_verified':dates==[day],**result});save()
 evaluated=[t for t in report['trades'] if t['status']=='evaluated']
 for hold in HOLDS:
  values=[p['price_change_pct'] for t in evaluated for p in t['paths'] if p['hold']==hold]
  report['comparisons'].append({'hold':hold,'count':len(values),'total':len(report['trades']),'mean_pct':round(sum(values)/len(values),2) if values else None,'win_rate':round(sum(v>0 for v in values)/len(values)*100,1) if values else None})
 report['excluded']=dict(Counter(t['reason'] for t in report['trades'] if t['status']=='excluded'))
 report['historical_date_verified_samples']=sum(t['historical_date_verified'] for t in report['trades'])
 for day in ['2026-06-16','2026-08-17','2026-09-16']:
  await call('kline_history',{'full_code':'000001.SZ','interval':'5','cq':'n','st':day.replace('-','')+'093000','et':day.replace('-','')+'100000','lt':20},day)
  report['coverage'][-1]['api']='kline_history / 5分钟 / 000001'
 report['complete']=True;save();await c.close()
if __name__=='__main__':asyncio.run(main())
