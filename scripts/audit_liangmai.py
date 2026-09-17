"""Read-only vendor audit. Credentials enter only via environment; reports contain metadata.
Usage: PYTHONPATH=backend python scripts/audit_liangmai.py --spec /path/openapi.json
"""
import argparse, asyncio, json, os, sys
from collections import Counter
from datetime import datetime
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.liangmai.client import LiangmaiClient
from app.config import get_settings
from app.services.interface_audit import inspect_response

async def run(spec_path,day,output,resume=False):
    spec=json.loads(Path(spec_path).read_text());output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    config=get_settings().model_copy(update={'liangmai_max_attempts':1,'liangmai_safe_rate':60,'liangmai_total_timeout':20,'liangmai_timeout':12})
    client=LiangmaiClient(config);await client.connect();results=[]
    if resume and output.exists():results=[r for r in json.loads(output.read_text())['items'] if r['status'] not in ('untested','error')]
    done={r['api'] for r in results};sem=asyncio.Semaphore(3)
    def save():
        report={'as_of':datetime.now().astimezone().isoformat(),'sample_date':day,'scope':'每接口一个文档示例样本；不代表完整覆盖或历史可用性', 'total':len(spec['paths']),'completed':len(results),'counts':dict(Counter(r['status'] for r in results)),'items':sorted(results,key=lambda r:r['api'])}
        tmp=output.with_suffix('.tmp');tmp.write_text(json.dumps(report,ensure_ascii=False,indent=2));tmp.replace(output)
    async def probe(path,op):
        api=op.get('operationId') or path.rsplit('/',1)[-1]
        if api in done:return
        params={};missing=[]
        for p in op.get('parameters',[]):
            key=p['name'];schema=p.get('schema',{})
            if key in ('token','api'):continue
            if not p.get('required'):continue
            if key in ('trade_date','tradeDate','date','startDate','endDate'):val=day
            elif key=='year':val=day[:4]
            elif key=='quarter':val='2'
            else:val=p.get('example',schema.get('default'))
            if val is None or val=='':missing.append(key)
            else:params[key]=val
        # Explicitly bound stock history responses; do not substitute current quotes for history.
        names={p['name'] for p in op.get('parameters',[])}
        if 'lt' in names:params['lt']=5
        if api=='kline_history':params.update(interval='d',cq='n',lt=100,et=day.replace('-',''))
        base={'api':api,'name':op.get('summary',api),'params':params,'history_parameters':[k for k in names if k in ('st','et','date','trade_date','tradeDate','startDate','endDate','year','quarter')]}
        if missing:results.append(base|{'status':'untested','reason':'缺少文档样本参数：'+','.join(missing)});save();return
        async with sem:
            r=await client.call(api,params,ttl=0)
        results.append(base|inspect_response(api,r,day))
        save();print(f'{len(results)}/{len(spec["paths"])} {api} {results[-1]["status"]}',flush=True)
    try:await asyncio.gather(*(probe(path,v['post']) for path,v in spec['paths'].items() if 'post' in v))
    finally:await client.close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--spec',required=True);p.add_argument('--day',required=True);p.add_argument('--output',default='data/research/interface_audit.json');p.add_argument('--resume',action='store_true');a=p.parse_args();asyncio.run(run(a.spec,a.day,a.output,a.resume))
