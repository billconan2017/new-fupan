"""Optional bounded, read-only reuse of the old SQLite daily warehouse."""
import sqlite3
import time
from pathlib import Path
from datetime import date
from app.liangmai.parsing import number


def read_daily(path: str, code: str, end: str, limit: int = 60):
    if not path:
        return {'ok': False, 'items': [], 'msg': '尚未配置本地历史库'}
    conn = None
    try:
        conn = sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro', uri=True, timeout=1)
        conn.row_factory = sqlite3.Row
        deadline = time.monotonic()+2
        conn.set_progress_handler(lambda: int(time.monotonic()>deadline), 1000)
        conn.execute('PRAGMA query_only=ON')
        # The known legacy schema uses ISO dates and an index on (code, trade_date).
        rows = conn.execute('''SELECT trade_date, open, high, low, close, source FROM stock_daily_kline
            WHERE code=? AND trade_date<=? ORDER BY trade_date DESC LIMIT ?''', (code,end,limit)).fetchall()
        items=[]
        for row in reversed(rows):
            d=dict(row)
            try:
                if date.fromisoformat(d['trade_date']).isoformat() > end:
                    continue
            except (ValueError, TypeError):
                continue
            for k in ('open','high','low','close'):
                d[k]=number(d[k])
            if any(d[k] is None or d[k]<=0 for k in ('open','high','low','close')):
                continue
            if d['low']>min(d['open'],d['close']) or d['high']<max(d['open'],d['close']):
                continue
            items.append(d)
        return {'ok': True, 'items': items, 'latest_date': items[-1]['trade_date'] if items else None,
                'source': 'legacy_sqlite_readonly', 'remote_calls': 0,
                'rejected_rows': len(rows)-len(items),
                'msg': '旧库历史日线，只读查询；复权口径与完整交易日覆盖未核验，不用于实时信号。'}
    except (sqlite3.Error, ValueError, OSError):
        return {'ok': False, 'items': [], 'msg': '本地历史库不可读、查询超时或表结构不匹配'}
    finally:
        if conn is not None:
            conn.close()
