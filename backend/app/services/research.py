"""A-share next-session preparation. Research evidence is not an execution record."""
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from app.services import workbench as wb
from app.services.data_evidence import SH
from app.liangmai.parsing import records,dragon_records,source_date

REPORT_DIR=Path(__file__).resolve().parents[3]/'data'/'research'

def trading_window(signal_day,calendar,entry='next_open'):
    days=sorted({d for x in calendar if (d:=source_date(x))})
    after=[d for d in days if d>signal_day]
    buy=after[0] if after else None
    return {'signal_date':signal_day,'buy_date':buy,'earliest_sell_date':after[1] if len(after)>1 else None,
            'entry':'次一交易日开盘后确认' if entry=='next_open' else entry,
            'holding_definition':'持有1日指买入后的第1个交易日卖出；买入当日不得卖出'}

def preparation_rows(ev):
    def payload(api):
        e=ev.get(api,{})
        return e.get('payload') if e.get('status') in ('ready','local') else []
    groups=[('涨停池',records(payload('stockpool_limit_up'))),('强势池',records(payload('stockpool_strong'))),('龙虎榜',dragon_records(payload('lhb_daily')))]
    out={};industries=defaultdict(set)
    for label,items in groups:
        for raw in items:
            code=wb.code_of(raw)
            if not code or not code.startswith(('00','30','60','68','43','83','87','88','92')):continue
            name=raw.get('mc') or raw.get('name') or raw.get('stockName') or code
            if 'ST' in str(name).upper() or '退' in str(name):continue
            r=out.setdefault(code,{'code':code,'name':name,'industry':'未归类','reasons':[],'amount':None,'price':None,'net_amount':None,'dragon_records':0,'risks':[]})
            if r['name']==code:r['name']=name
            if label not in r['reasons']:r['reasons'].append(label)
            industry=raw.get('hy') or raw.get('hybk') or raw.get('industry')
            if industry:r['industry']=industry;industries[industry].add(code)
            if label!='龙虎榜':
                amt=wb.value(raw,'cje','amount');price=wb.value(raw,'p','price')
                if amt is not None:r['amount']=amt
                if price is not None:r['price']=price
            else:
                r['dragon_records']+=1
                # Different listing reasons may repeat the same turnover. Never sum them.
                net=wb.value(raw,'net_amount','netAmount','netBuyAmt')
                if r['dragon_records']==1:r['net_amount']=net
                elif net!=r['net_amount']:r['net_amount']=None
    for r in out.values():
        r['overlap']=len(r['reasons']);r['industry_count']=len(industries.get(r['industry'],set()))
        if '涨停池' in r['reasons']:r['risks'].append('涨停后次日可能无法买入，需检查开盘与封单')
        if r['dragon_records']>1:r['risks'].append('多条上榜记录，不重复累加资金')
        if r['price'] is None:r['risks'].append('缺少可靠参考价格')
        r['risks'].append('隔夜消息与次日竞价尚未确认')
    return sorted(out.values(),key=lambda r:(r['overlap'],r['industry_count'],r['amount'] or 0),reverse=True)

async def preparation(day):
    ev=await wb.evidence(day)
    cal=(ev.get('basic_trade_calendar',{}).get('payload') or [])+(ev.get('calendar_next_year',{}).get('payload') or [])
    window=trading_window(day,cal)
    now=datetime.now(SH)
    provisional=day==now.date().isoformat() and now.strftime('%H:%M')<'17:10'
    sources=[{'api':api,'name':name,'status':ev.get(api,{}).get('status','untested'),'rows':ev.get(api,{}).get('row_count',0),'fetched_at':ev.get(api,{}).get('fetched_at')} for api,name in [('stockpool_limit_up','涨停池'),('stockpool_strong','强势池'),('stockpool_broken_board','炸板池'),('lhb_daily','龙虎榜')]]
    return {'window':window,'rows':preparation_rows(ev),'sources':sources,'provisional':provisional,'rule_version':'ashare-preparation-v1',
            'note':'候选按证据交集数、行业聚集数、成交额排序；不是收益预测。历史候选重建不等于当时发出的推荐。龙虎榜仅作资金关注线索，未自动判定买点。',
            'ready_for_decision':not provisional and all(s['status'] in ('ready','local','empty') for s in sources) and bool(window['buy_date'])}

def audit_report():
    p=REPORT_DIR/'interface_audit.json'
    if not p.exists():return {'items':[],'total':255,'completed':0,'counts':{},'scope':'尚未运行目录审计'}
    return json.loads(p.read_text())

def history_report():
    p=REPORT_DIR/'history_study.json'
    if not p.exists():return {'coverage':[],'comparisons':[],'note':'尚无可用的历史研究结果；不能据此判断最佳持有期。'}
    return json.loads(p.read_text())

def entry_policy(day,now=None,is_trade_day=False):
    now=now or datetime.now(SH)
    if day!=now.date().isoformat():return {'state':'historical','entry_allowed':False,'label':'历史研究 · 不生成实时入场提示'}
    if not is_trade_day:return {'state':'closed','entry_allowed':False,'label':'交易日未确认或休市 · 不生成实时入场提示'}
    hm=now.strftime('%H:%M')
    if hm<'09:26':return {'state':'prepare','entry_allowed':False,'label':'等待竞价结果 · 先核对昨日候选与热点'}
    if hm<'09:30':return {'state':'confirm','entry_allowed':False,'label':'竞价结果确认 · 尚未进入开盘后观察窗口'}
    if hm<'10:00':return {'state':'entry','entry_allowed':True,'label':'9:30—10:00 入场观察窗口 · 仍需核验实时价格与可成交性'}
    return {'state':'tracking','entry_allowed':False,'label':'已过10:00入场截止 · 转入持仓跟踪与次日准备'}
