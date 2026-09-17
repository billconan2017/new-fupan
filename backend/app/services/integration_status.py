"""Read-only scheduler and storage inventory. No job execution or credential output."""
import json,os,re,sqlite3,time
from pathlib import Path
from datetime import datetime
from app.services.data_evidence import SH

TABLES=(('stock_daily_kline','日线'),('stock_lhb_detail_local','龙虎榜明细'),('intraday_selection_result','旧选股记录'),('blogger_daily_views','博主观点'))
_cache={}

def task_summary(rows):
    tasks=[]
    for r in rows:
        if not re.search('股票|复盘|行情|龙虎|淘股',str(r.get('name',''))):continue
        err=str(r.get('last_error') or '')
        missing=re.search(r"No module named ['\"]([\w.]+)['\"]",err)
        reason='缺少依赖：'+missing[1] if missing else '数据量校验未通过' if 'rows=0' in err else '执行失败，需检查本机日志' if r.get('last_status')=='error' else ''
        tasks.append({'name':r.get('name'),'enabled':bool(r.get('enabled')),'schedule':(r.get('schedule') or {}).get('expr'),
            'last_run':r.get('last_run_at'),'next_run':r.get('next_run_at'),'status':r.get('last_status','unknown'),
            'failures':r.get('failure_streak',0),'reason':reason})
    return tasks

def sqlite_coverage(path,day):
    out=[]
    if not path or not Path(path).is_file():return out
    with sqlite3.connect(f'file:{Path(path).resolve()}?mode=ro',uri=True,timeout=1) as c:
        for table,name in TABLES:
            deadline=time.monotonic()+.7;c.set_progress_handler(lambda: int(time.monotonic()>deadline),5000)
            try:
                latest=c.execute(f'SELECT trade_date FROM {table} ORDER BY trade_date DESC LIMIT 1').fetchone()
                count=c.execute(f'SELECT count(*) FROM {table} WHERE trade_date=?',(day,)).fetchone()[0]
                out.append({'name':name,'table':table,'store':'旧SQLite','latest':latest[0] if latest else None,'day_rows':count,'status':'read'})
            except sqlite3.Error:out.append({'name':name,'store':'旧SQLite','latest':None,'day_rows':None,'status':'unavailable'})
    return out

def postgres_coverage(dsn,day):
    if not dsn:return []
    import psycopg2
    out=[]
    try:
        with psycopg2.connect(dsn,connect_timeout=2,options='-c default_transaction_read_only=on -c statement_timeout=2500') as c:
            for table,name in TABLES:
                try:
                    with c.cursor() as q:
                        q.execute(f'SELECT trade_date FROM {table} ORDER BY trade_date DESC LIMIT 1');latest=q.fetchone()
                        q.execute(f'SELECT count(*) FROM {table} WHERE trade_date=%s',(day,));count=q.fetchone()[0]
                        out.append({'name':name,'table':table,'store':'旧PostgreSQL','latest':str(latest[0]) if latest else None,'day_rows':count,'status':'read'})
                except psycopg2.Error:
                    c.rollback();out.append({'name':name,'store':'旧PostgreSQL','latest':None,'day_rows':None,'status':'unavailable'})
    except psycopg2.Error:out.append({'name':'旧数据库连接','store':'旧PostgreSQL','status':'unavailable','day_rows':None,'latest':None})
    return out

def legacy_candidates(path,day):
    if not path or not Path(path).is_file():return []
    with sqlite3.connect(f'file:{Path(path).resolve()}?mode=ro',uri=True,timeout=1) as c:
        c.row_factory=sqlite3.Row
        rows=c.execute("""SELECT stock_code,stock_name,stage,status,score,industry,selected_time,reason_text
            FROM intraday_selection_result WHERE trade_date=? AND stage IN ('confirm1000','accept945','accept931')
            ORDER BY CASE stage WHEN 'confirm1000' THEN 0 WHEN 'accept945' THEN 1 ELSE 2 END, rank_no LIMIT 60""",(day,)).fetchall()
        unique={}
        for r in rows:
            code=r['stock_code'].split('.')[0]
            if re.fullmatch(r'\d{6}',code) and code not in unique:unique[code]=dict(r)|{'code':code}
        return list(unique.values())[:5]

def report(day):
    cached=_cache.get(day)
    if cached and time.monotonic()-cached[0]<30:return cached[1]
    tasks=[];path=os.environ.get('LEGACY_CRON_FILE');scheduler='未配置'
    if path:
        try:tasks=task_summary(json.loads(Path(path).read_text()).get('jobs',[]));scheduler='已读取Hermes任务配置'
        except (OSError,ValueError):scheduler='任务配置暂不可读'
    db=os.environ.get('LEGACY_MARKET_DB');coverage=sqlite_coverage(db,day)+postgres_coverage(os.environ.get('LEGACY_PG_DSN'),day)
    try:candidates=legacy_candidates(db,day)
    except sqlite3.Error:candidates=[]
    result={'day':day,'checked_at':datetime.now(SH).isoformat(),'scheduler':scheduler,'tasks':tasks,'coverage':coverage,'legacy_candidates':candidates,
      'enabled':sum(r['enabled'] for r in tasks),'errors':sum(r['enabled'] and r['status']=='error' for r in tasks),
      'note':'定时任务执行成功不等于数据完整。旧SQLite、旧PostgreSQL和新版证据库分别核验；只读查看，不触发推送或补采。',
      'dependency_repair':('Hermes运行环境已补装beautifulsoup4和psycopg2-binary；历史失败记录保留，下次运行结果待验证。' if os.environ.get('LEGACY_DEPENDENCIES_REPAIRED')=='1' else '依赖修复状态未登记；执行成功不等于数据完整。')}
    _cache.clear();_cache[day]=(time.monotonic(),result)
    return result
