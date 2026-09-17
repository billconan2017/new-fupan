"""Metadata-only capability evidence; successful calls are not trading readiness."""
from collections import Counter
from app.liangmai.parsing import records, dragon_records, snapshot_records, source_date
from app.services.data_evidence import freshness
from app.services.data_evidence import quote_time

DATE_FIELDS = ('t', 'time', 'trade_date', 'tradeDate', 'date', 'date1', 'endDate')

def merge_quotes(snapshot, targeted, day):
    """Replace whole rows only with newer valid timestamps; never blend old fields."""
    out={r['code']:r for r in snapshot_records(snapshot)}
    for r in snapshot_records(targeted):
        stamp=quote_time(r.get('t'))
        old=quote_time(out.get(r['code'],{}).get('t'))
        if stamp and stamp.date().isoformat()==day and (old is None or stamp>=old):
            out[r['code']]=r
    return list(out.values())

def inspect_response(api, result, day, now=None):
    data = result.get('data')
    rows = dragon_records(data) if api == 'lhb_daily' else snapshot_records(data) if api.startswith('market_quote') or api == 'market_snapshot_all' else records(data)
    if not rows and isinstance(data, dict) and any(k in data for k in DATE_FIELDS):
        rows = [data]
    dates = sorted({d for r in rows for k in DATE_FIELDS if (d := source_date(r.get(k)))})
    stamps = [r.get('t') or r.get('time') for r in rows]
    quote_states = dict(Counter(freshness(t, day, now)['state'] for t in stamps)) if api.startswith('market_quote') or api == 'market_snapshot_all' else {}
    count = len(rows) if rows else len(data) if isinstance(data, (dict,list)) else 0
    return {'status': ('ready' if count else 'empty') if result.get('ok') else 'error',
            'rows_or_keys':count, 'fields': sorted({k for r in rows for k in r})[:80],
            'first_date':dates[0] if dates else None,'last_date':dates[-1] if dates else None,
            'date_check':'contains_requested' if day in dates else 'other_dates' if dates else 'unverified',
            'quote_states':quote_states,'code':result.get('code'),
            'elapsed_ms':result.get('_meta',{}).get('elapsedMs'),
            'reason':result.get('msg','')}

def enrich_report(report, catalog, focused=None):
    items=[]
    for item in report.get('items',[]):
        meta=catalog['endpoints'].get(item['api'],{})
        items.append({**item,'category':meta.get('category','未分类')})
    groups={}
    for r in items:
        counts=groups.setdefault(r['category'],{'total':0,'ready':0,'empty':0,'error':0,'untested':0})
        counts['total']+=1
        counts[r['status']]=counts.get(r['status'],0)+1
    return {**report,'items':items,'categories':groups,'focused':focused or {}}
