"""Task-specific data readiness, independent of endpoint smoke-test success."""
from datetime import datetime
from app.services.data_evidence import SH,freshness
from app.services.recent_replay import valid_bar
from app.services.workbench import code_of
from app.liangmai.parsing import records,snapshot_records,dragon_records,source_date,number

def assess(day,ev,now=None):
    now=now or datetime.now(SH)
    def payload(key):
        e=ev.get(key,{})
        return e.get('payload') if e.get('status') in ('ready','local') else []
    cal=sorted({d for x in (payload('basic_trade_calendar') or [])+(payload('calendar_previous_year') or [])+(payload('calendar_next_year') or []) if (d:=source_date(x))})
    previous=max((d for d in cal if d<day),default=None)
    identities={code_of(r) for r in records(payload('basic_stock_list'))}
    q=[r for r in snapshot_records(payload('market_snapshot_all')) if source_date(r.get('t'))==day and code_of(r) in identities]
    stamps=sorted(str(r['t']) for r in q)
    latest=stamps[-1] if stamps else None
    state=freshness(latest,day,now)
    quote_note='；本次刷新失败，使用同日本地旧行情' if ev.get('market_snapshot_all',{}).get('status')=='local' else ''
    quote_complete=sum(all(number(r.get(k)) is not None for k in ('p','o','pc','cje','lb')) and number(r['p'])>0 and number(r['o'])>0 for r in q)
    timely=sum(freshness(r.get('t'),day,now)['state'] in ('fresh','history') for r in q)
    auction=[r for r in records(payload('auction_morning_grab_amount')) if source_date(r.get('time'))==day]
    auction_complete=sum(all(number(r.get(k)) is not None for k in ('qczf','qccje','qcwtje')) for r in auction)
    expected={day+' '+t for t in ('09:35:00','09:40:00','09:45:00','09:50:00','09:55:00','10:00:00')}
    minute_keys=[k for k in ev if k.startswith('minute_5:')]
    minute_ok=sum(expected.issubset({str(r.get('t')) for r in records(payload(k)) if valid_bar(r)}) for k in minute_keys)
    stop_keys=[k for k in ev if k.startswith('limit_prices:')]
    stop_ok=sum(any(source_date(r.get('t'))==day and number(r.get('h')) and number(r.get('l')) for r in records(payload(k))) for k in stop_keys)
    histories=[k for k in ev if k.startswith('kline_history:')]
    required=set(d for d in cal if previous and d<=previous)
    required=set(sorted(required)[-65:])
    history_ok=sum(len(required)==65 and required.issubset({source_date(r.get('t')) for r in records(payload(k)) if (number(r.get('c')) or 0)>0 and (number(r.get('h')) or 0)>0}) for k in histories)
    pool_keys=['stockpool_limit_up','stockpool_strong','stockpool_broken_board','lhb_daily']
    from app.services.research import collected_after_close
    after_close=collected_after_close(day,ev,pool_keys)
    pools=sum(ev.get(k,{}).get('status') in ('ready','local','empty') for k in pool_keys)
    items=[
      {'key':'calendar','name':'交易日与T+1','status':'ready' if day in cal and previous and len([d for d in cal if d>day])>=2 else 'missing','value':f'{len(cal)}个日历日期','detail':'需定位前日、下一买入日及最早卖出日','action':'review'},
      {'key':'quote','name':'A股行情快照','status':'ready' if q and quote_complete==len(q) and timely==len(q) else 'partial' if q else 'missing','value':f'{quote_complete}/{len(q)}条关键字段齐全','detail':f"源时间 {latest or '缺失'} · {state['label']}{quote_note}；逐条时效通过 {timely}/{len(q)}，不以最新一条代表全体",'action':'quote' if day==now.date().isoformat() else None},
      {'key':'auction','name':'竞价确认','status':'ready' if auction_complete and auction_complete==len(auction) else 'partial' if auction else 'missing','value':f'{auction_complete}/{len(auction)}条可评分','detail':'约9:26后排行样本，不是9:25前的实时竞价流，也不是全市场','action':'pre'},
      {'key':'review','name':'盘后备选证据','status':'ready' if pools==4 and after_close and not any(ev.get(k,{}).get('status')=='local' for k in pool_keys) else 'partial' if pools else 'missing','value':f'{pools}/4项有记录','detail':'涨停、强势、炸板、龙虎榜；须盘后重新采集，本地降级和源日期仍需核对','action':'review'},
      {'key':'minute','name':'10点前五分钟线','status':'ready' if minute_keys and minute_ok==len(minute_keys) else 'partial' if minute_ok else 'missing','value':f'{minute_ok}/{len(minute_keys)}只早盘6根齐全','detail':'仅已采样股票；缺根不补零，盘中未完成窗口会显示不足','action':'execution'},
      {'key':'limits','name':'涨跌停价核验','status':'ready' if stop_keys and stop_ok==len(stop_keys) else 'partial' if stop_ok else 'missing','value':f'{stop_ok}/{len(stop_keys)}只匹配所选日期','detail':'接口非空但只返回旧日期，也按缺失处理，不能确认成交','action':'execution'},
      {'key':'history','name':'趋势日线','status':'ready' if histories and history_ok==len(histories) else 'partial' if history_ok else 'missing','value':f'{history_ok}/{len(histories)}只连续65日齐全','detail':'截至前一交易日；只是已选样本，尚未全市场补齐','action':'history'},
    ]
    gaps=[x['name'] for x in items if x['status']!='ready']
    return {'day':day,'checked_at':now.isoformat(),'items':items,'ready':sum(i['status']=='ready' for i in items),'total':len(items),'gaps':gaps,
            'verdict':'尚不足以支撑完整实盘与可靠回测' if gaps else '所测样本关键字段齐全；仍未证明全市场覆盖或成交可得性',
            'automation':'独立定时器负责交易日采集，不依赖页面打开；具体执行结果见自动采集记录',
            'limits':['未接入9:25前逐笔竞价确认','没有券商真实持仓、委托和成交回报','样本外验证与组合资金回测尚未完成']}

async def build(day):
    from app.services.workbench import evidence
    from app.services.research import preparation_rows
    ev=await evidence(day);r=assess(day,ev)
    r['sample_codes']=[row['code'] for row in preparation_rows(ev)[:5]]
    r['sample_names']=[row['name'] for row in preparation_rows(ev)[:5]]
    return r
