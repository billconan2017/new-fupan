"""Explicit source shapes. Missing values remain None, never invented zeroes."""
from datetime import datetime
import math
import re


def number(value):
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None


def source_date(value):
    raw = str(value or '')
    for fmt, size in (('%Y-%m-%d', 10), ('%Y%m%d', 8)):
        try:
            return datetime.strptime(raw[:size], fmt).date().isoformat()
        except ValueError:
            pass
    return None


def records(data):
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ('list', 'items', 'todayList'):
            if isinstance(data.get(key), list):
                return records(data[key])
    return []


def emotion_for_date(data, trade_date):
    if isinstance(data, dict) and isinstance(data.get('colNameList'), list):
        columns = data['colNameList']
        candidates = [dict(zip(columns, r)) for r in data.get('contentList', [])
                      if isinstance(r, list) and len(r) == len(columns)]
    else:
        candidates = records(data)
    for row in candidates:
        if source_date(row.get('date1', row.get('trade_date', row.get('date')))) == trade_date:
            return row
    return None


def snapshot_records(data):
    rows = records(data)
    if not rows and isinstance(data, dict):
        # Only code-keyed mappings are supported; array positions are not codes.
        rows = [{**v, 'code': k} for k, v in data.items()
                if isinstance(v, dict) and re.fullmatch(r'\d{6}(?:\.(?:SH|SZ|BJ))?', k)]
    result = []
    for row in rows:
        code = str(row.get('dm') or row.get('code') or row.get('c') or '').split('.')[0]
        if re.fullmatch(r'\d{6}', code):
            result.append({**row, 'code': code})
    return result


def dragon_records(data):
    rows = records(data)
    if not rows and isinstance(data, dict):
        # lhb_daily may group records under distinct listing-reason arrays.
        rows = [r for v in data.values() if isinstance(v, list) for r in v if isinstance(r, dict)]
    return [r for r in rows if r.get('thsCode') or r.get('code') or r.get('dm')]
