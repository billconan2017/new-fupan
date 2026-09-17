from datetime import date, datetime
from typing import Literal
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import text
import json
from app.database import engine
from app.services import workbench as service
from app.services.data_evidence import SH

router=APIRouter(prefix='/api/workbench',tags=['workbench'])

@router.get('/screen')
async def screen(day: date | None=None,phase: Literal['pre','live','review']='live',mode: Literal['short','trend']='short'):
    return await service.build((day or datetime.now(SH).date()).isoformat(),phase,mode)

class Collection(BaseModel):
    model_config=ConfigDict(extra='forbid')
    day: date
    stage: Literal['pre','live','review','history','quote','execution','watchquote']
    codes: list[str]=Field(default_factory=list,max_length=20)

@router.post('/collect')
async def collect(body: Collection):
    if body.day>datetime.now(SH).date():raise HTTPException(422,'不能采集未来日期')
    if body.stage in ('quote','watchquote') and body.day!=datetime.now(SH).date():raise HTTPException(422,'行情只支持当前日期')
    if body.stage in ('history','execution','watchquote') and (not body.codes or any(len(c)!=6 or not c.isdigit() for c in body.codes)):
        raise HTTPException(422,'请选择1至20只六位股票代码')
    return await service.start_job(body.day.isoformat(),body.stage,list(dict.fromkeys(body.codes)))

@router.get('/jobs/{job_id}')
async def job(job_id:str):
    async with engine.connect() as c:
        row=(await c.execute(text('SELECT * FROM wb_jobs WHERE id=:id'),{'id':job_id})).mappings().first()
    if not row:raise HTTPException(404,'任务不存在')
    return dict(row)

class Plan(BaseModel):
    model_config=ConfigDict(extra='forbid')
    day:date
    code:str=Field(pattern=r'^\d{6}$')
    mode:Literal['short','trend']
    phase:Literal['pre','live','review']
    note:str=Field(default='',max_length=1000)

@router.post('/plans')
async def add_plan(body:Plan):
    from fastapi.encoders import jsonable_encoder
    result=await service.build(body.day.isoformat(),body.phase,body.mode)
    row=next((r for r in result['rows'] if r['code']==body.code),None)
    if not row:raise HTTPException(409,'此日期和阶段暂无该标的证据，请重新加载')
    frozen={'rule_version':service.RULE_VERSION,'row':row,'previous_date':result['previous_date'],'source_collection_time':result['quote_time']}
    async with engine.begin() as c:
        saved=(await c.execute(text('''INSERT INTO wb_plans(trade_date,code,name,mode,phase,note,evidence)
          VALUES(:d,:code,:name,:mode,:phase,:note,CAST(:evidence AS JSONB))
          ON CONFLICT(trade_date,code,mode,phase) DO NOTHING RETURNING id'''),
          {'d':body.day.isoformat(),'code':body.code,'name':row['name'],'mode':body.mode,'phase':body.phase,'note':body.note,
           'evidence':json.dumps(jsonable_encoder(frozen),ensure_ascii=False)})).scalar()
    return {'ok':True,'created':bool(saved),'message':'已冻结观察依据' if saved else '已在观察计划中，原始依据保持不变'}

@router.get('/plans')
async def plans(day: date):
    async with engine.connect() as c:
        items=(await c.execute(text('SELECT * FROM wb_plans WHERE trade_date<=:d ORDER BY created_at DESC LIMIT 200'),{'d':day.isoformat()})).mappings().all()
    current=await service.build(day.isoformat(),'live','short');prices={r['code']:r for r in current['rows']}
    result=[]
    for p in items:
        item=dict(p);frozen=item['evidence']['row'];now=prices.get(item['code'],{});base=frozen.get('price');price=now.get('price')
        # Same-day historical queries must not evaluate before the frozen source timestamp.
        chronological=now.get('source_at') and frozen.get('source_at') and str(now['source_at'])>=str(frozen['source_at'])
        item.update({'evaluation_date':day.isoformat(),'current_price':price,'reference_price':base,
            'change_since_saved':round((price/base-1)*100,2) if price is not None and base and chronological else None,
            'current_source_at':now.get('source_at')})
        result.append(item)
    return {'items':result,'note':'相对冻结报价的价格变化，不含交易费用，也不代表真实持仓收益。'}

@router.get('/history/{code}')
async def history(code:str,day:date):
    if len(code)!=6 or not code.isdigit():raise HTTPException(422,'股票代码无效')
    ev=await service.evidence(day.isoformat());data=ev.get('kline_history:'+code,{})
    return {'items':data.get('payload') or [],'status':data.get('status','untested'),'fetched_at':data.get('fetched_at'),'adjustment':'前复权'}

@router.get('/preparation')
async def preparation(day:date):
    if day>datetime.now(SH).date():raise HTTPException(422,'不能使用未来盘后数据')
    from app.services.research import preparation as build_preparation
    return await build_preparation(day.isoformat())

@router.get('/interface-audit')
async def interface_audit():
    from app.services.research import audit_report
    return audit_report()

@router.get('/legacy-research')
def legacy_research(day:date):
    from app.services.legacy_research import report
    return report(day.isoformat())

@router.get('/history-study')
async def history_study():
    from app.services.research import history_report
    return history_report()

@router.post('/preparation/plans')
async def freeze_preparation(body:Plan):
    from app.services.research import preparation as build_preparation
    from fastapi.encoders import jsonable_encoder
    if body.phase!='review' or body.day>datetime.now(SH).date():raise HTTPException(422,'只接受已发生日期的盘后备选')
    report=await build_preparation(body.day.isoformat())
    row=next((r for r in report['rows'] if r['code']==body.code),None)
    if row is None:raise HTTPException(409,'当前证据中没有该候选')
    if not report['ready_for_decision']:raise HTTPException(409,'盘后证据尚未齐备或交易日历不足，请先补齐；临时候选不能冻结为正式计划')
    frozen={'rule_version':report['rule_version'],'row':{**row,'source_at':None},'window':report['window'],'sources':report['sources'],
            'reconstruction':body.day!=datetime.now(SH).date(),'execution_status':'未成交，仅观察计划'}
    async with engine.begin() as c:
        saved=(await c.execute(text('''INSERT INTO wb_plans(trade_date,code,name,mode,phase,note,evidence)
            VALUES(:d,:code,:name,:mode,'review',:note,CAST(:evidence AS JSONB))
            ON CONFLICT(trade_date,code,mode,phase) DO NOTHING RETURNING id'''),
            {'d':body.day.isoformat(),'code':body.code,'name':row['name'],'mode':body.mode,'note':body.note,
             'evidence':json.dumps(jsonable_encoder(frozen),ensure_ascii=False)})).scalar()
    return {'created':bool(saved),'message':'备选依据和 T+1 日期已冻结（非成交）' if saved else '已存在，保留原始依据'}

@router.get('/recent-replay')
async def recent_replay():
    from app.services.research import REPORT_DIR
    p=REPORT_DIR/'recent_replay.json'
    return json.loads(p.read_text()) if p.exists() else {'complete':False,'trades':[],'note':'尚未运行近五日回溯'}

@router.get('/readiness')
async def readiness(day:date):
    from app.services.readiness import build
    return await build(day.isoformat())
