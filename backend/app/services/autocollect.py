"""Standalone collection schedule. Invoked by a local systemd timer, never Hermes."""
from datetime import datetime
from sqlalchemy import text
from app.database import engine
from app.services.data_evidence import SH
from app.services import workbench as wb
from app.liangmai.parsing import source_date

SCHEDULE = [
 ('09:26', 'pre', '竞价截面'), ('15:45', 'review', '收盘复盘'),
 ('17:30', 'review', '盘后补齐'), ('20:30', 'review', '晚间补齐'),
 ('22:00', 'review', '最终补齐'),
]

def slots(now):
    """No replay of missed real-time signals. EOD may catch up to the latest slot."""
    if now.weekday() >= 5: return []
    hm=now.strftime('%H:%M')
    if '09:26' <= hm < '09:30': return [('09:26','pre')]
    if '09:30' <= hm <= '11:30' or '13:00' <= hm <= '15:00':
        minute=now.minute-now.minute%5
        return [(f'{now.hour:02d}:{minute:02d}','live'),(f'{now.hour:02d}:{minute:02d}','intraday')]
    due=[(t,s) for t,s,_ in SCHEDULE if s=='review' and t<=hm]
    return [(due[-1][0],stage) for stage in ('review','intraday','history')] if due else []

def shortlist(rows):
    codes=[];industries={}
    for r in rows:
        if r['score'] is None or r['in_pool'] or r['pct_chg'] is None or not 0<=r['pct_chg']<=7 or 'ST' in r['name'].upper() or '退' in r['name']:continue
        industry=r.get('industry') or '未归类'
        if industries.get(industry,0)>=2:continue
        codes.append(r['code']);industries[industry]=industries.get(industry,0)+1
        if len(codes)==5:break
    return codes

async def tick(now=None):
    now=now or datetime.now(SH); day=now.date().isoformat()
    due=slots(now)
    if not due:return {'state':'outside_schedule'}
    # A dedicated session lock prevents overlapping timer/manual ticks.
    async with engine.connect() as guard:
        if not (await guard.execute(text('SELECT pg_try_advisory_lock(889920026)'))).scalar():return {'state':'busy'}
        try:
            ev=await wb.evidence(day)
            calendar=ev.get('basic_trade_calendar',{})
            if calendar.get('status')!='ready':
                result=await wb.liangmai.call('basic_trade_calendar',{'year':day[:4]},ttl=3600)
                await wb.save_evidence('basic_trade_calendar',day,result)
                calendar=(await wb.evidence(day)).get('basic_trade_calendar',{})
            if calendar.get('status')!='ready':return {'state':'calendar_unavailable'}
            if day not in {source_date(r) for r in (calendar.get('payload') or [])}:return {'state':'closed'}
            for slot,stage in due:
                key=f'{day}:{slot}:{stage}'
                async with engine.connect() as c:
                    prior=(await c.execute(text('SELECT s.job_id,s.attempts,j.status,j.created_at FROM wb_schedule_runs s JOIN wb_jobs j ON j.id=s.job_id WHERE slot=:key'),{'key':key})).first()
                if prior and (prior.status!='failed' or prior.attempts>=3 or (now-prior.created_at).total_seconds()<300):continue
                codes=[]
                if stage in ('intraday','history'):
                    screen=await wb.build(day)
                    codes=shortlist(screen['rows'])
                    if not codes:continue
                result=await wb.start_job(day,stage,codes)
                if not result['ok']:return {'state':'busy'}
                async with engine.begin() as c:
                    await c.execute(text('INSERT INTO wb_schedule_runs(slot,job_id,stage) VALUES(:slot,:job,:stage) ON CONFLICT(slot) DO UPDATE SET job_id=EXCLUDED.job_id,attempts=wb_schedule_runs.attempts+1'),{'slot':key,'job':result['job_id'],'stage':stage})
                return {'state':'started','stage':stage,'job_id':result['job_id']}
            return {'state':'already_run'}
        finally:
            await guard.execute(text('SELECT pg_advisory_unlock(889920026)'))

async def status():
    async with engine.connect() as c:
        rows=(await c.execute(text('''SELECT s.slot,s.stage,j.status,j.progress,j.total,j.results,j.created_at,j.finished_at
          FROM wb_schedule_runs s JOIN wb_jobs j ON j.id=s.job_id ORDER BY s.created_at DESC LIMIT 30'''))).mappings().all()
    runs=[]
    for row in rows:
        r=dict(row)
        if r['status']=='done' and any(x.get('status') not in ('ready','local') for x in r['results']):r['status']='partial'
        r.pop('results',None);runs.append(r)
    return {'owner':'systemd','schedule':[{'time':t,'stage':s,'name':n} for t,s,n in SCHEDULE],
            'intraday':'交易日09:30–11:30、13:00–15:00，每5分钟行情与重点分时',
            'runs':runs,'note':'休市不采集；缺失明确展示。错过的竞价不以当前行情补造。'}
