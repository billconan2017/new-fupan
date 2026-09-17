"""Bounded Liangmai probes by trading use case; credentials only from environment."""
import argparse, asyncio, json, sys
from datetime import datetime
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.config import get_settings
from app.liangmai.client import LiangmaiClient
from app.services.interface_audit import inspect_response
from app.services.data_evidence import SH

def cases(days):
    today=days[0]
    for api,p in [('market_snapshot_all',{}),('market_quote_all',{}),('market_quote',{'ts_code':'600519'}),('market_quote_pro',{'ts_code':'600519'}),('market_quote_multi',{'stock_codes':'600519,000001,000759'})]:
        yield '实时行情',api,p,today
    for day in days:
        for api in ('stockpool_limit_up','stockpool_broken_board','stockpool_strong'):
            yield '情绪与热点',api,{'trade_date':day},day
        yield '龙虎榜', 'lhb_daily',{'date':day},day
        yield '竞价', 'auction_morning_grab_amount',{'tradeDate':day,'period':'0','type':'1'},day
        yield '板块竞价', 'auction_morning_sector_pro',{'tradeDate':day},day
        for code in ('000001','000759','600519'):
            for interval in ('1','5','d'):
                start=day.replace('-','')+('093000' if interval!='d' else '')
                end=day.replace('-','')+('100000' if interval!='d' else '')
                yield '分钟与日线','kline_history',{'full_code':code,'interval':interval,'cq':'n','st':start,'et':end,'lt':35},day
            yield '成交约束','kline_stop_price_history',{'full_code':code,'st':day.replace('-',''),'et':day.replace('-',''),'lt':5},day

async def run(days,output):
    config=get_settings().model_copy(update={'liangmai_max_attempts':1,'liangmai_safe_rate':60,'liangmai_total_timeout':18,'liangmai_timeout':12})
    client=LiangmaiClient(config);await client.connect()
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    report={'as_of':datetime.now(SH).isoformat(),'days':days,'scope':'定向股票与日期样本，覆盖与权限仅代表本次实测；非全市场可用性保证','items':[]}
    try:
        for category,api,params,day in cases(days):
            response=await client.call(api,params,ttl=0)
            r={'category':category,'api':api,'params':params,'sample_date':day,**inspect_response(api,response,day)}
            report['items'].append(r)
            temp=output.with_suffix('.tmp');temp.write_text(json.dumps(report,ensure_ascii=False,indent=2));temp.replace(output)
            print(api,day,r['status'],r['rows_or_keys'],r['date_check'],flush=True)
    finally:await client.close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--days',nargs='+',required=True);p.add_argument('--output',default='data/research/trading_capability_audit.json');a=p.parse_args()
    asyncio.run(run(a.days,a.output))
