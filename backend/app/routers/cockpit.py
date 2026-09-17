"""Review → next available day's observation, with explicit evidence boundaries."""
from datetime import date, datetime
from fastapi import APIRouter, Query
from sqlalchemy import text
from app.database import engine
from app.services.data_evidence import SH, freshness
from app.services.review_service import generate_review_snapshot

router = APIRouter(prefix='/api/cockpit', tags=['cockpit'])


@router.get('/summary')
async def summary(day: date | None = Query(None)):
    target = (day or datetime.now(SH).date()).isoformat()
    async with engine.connect() as conn:
        previous = (await conn.execute(text('SELECT MAX(trade_date) FROM limit_up_pool WHERE trade_date < :d'), {'d': target})).scalar()
        available_dates = (await conn.execute(text('SELECT DISTINCT trade_date FROM limit_up_pool ORDER BY trade_date DESC LIMIT 60'))).scalars().all()
        latest = (await conn.execute(text('SELECT MAX(snapshot_at) FROM market_snapshot WHERE trade_date=:d'), {'d': target})).scalar()
        rows = []
        if previous:
            result = await conn.execute(text('''
                WITH candidates AS (
                    SELECT DISTINCT ON (code) code, name, consecutive, industry, limit_reason
                    FROM limit_up_pool WHERE trade_date=:p ORDER BY code, consecutive DESC NULLS LAST
                ), today_pool AS (
                    SELECT DISTINCT ON (code) code, consecutive FROM limit_up_pool
                    WHERE trade_date=:d ORDER BY code, consecutive DESC NULLS LAST
                )
                SELECT c.*, q.price, q.pct_chg, q.source_at, q.snapshot_at,
                    t.code IS NOT NULL AS in_today_limit_up, t.consecutive AS today_consecutive
                FROM candidates c
                LEFT JOIN LATERAL (
                    SELECT price, pct_chg, source_at, snapshot_at FROM market_snapshot
                    WHERE trade_date=:d AND snapshot_at=:s AND code=c.code ORDER BY id DESC LIMIT 1
                ) q ON TRUE
                LEFT JOIN today_pool t ON t.code=c.code
                ORDER BY c.consecutive DESC NULLS LAST, c.code
            '''), {'p': previous, 'd': target, 's': latest})
            rows = [dict(r._mapping) for r in result]
        snap = (await conn.execute(text('''SELECT COUNT(*) AS rows, MIN(source_at) AS oldest_source_at,
            MAX(source_at) AS newest_source_at, COUNT(*) FILTER (WHERE source_at IS NULL) AS unknown_time
            FROM market_snapshot WHERE trade_date=:d AND snapshot_at=:s'''), {'d': target, 's': latest})).mappings().first()
    for row in rows:
        row['quote_status'] = freshness(row['source_at'], target)
        row['observation'] = '在目标日涨停池' if row['in_today_limit_up'] else '未在目标日已入库涨停池；不能据此认定断板'
    matched = sum(r['price'] is not None for r in rows)
    return {'ok': True, 'date': target, 'available_dates': available_dates,
            'baseline_date': previous, 'baseline_note': '基准为本地最近有涨停记录的更早日期；不保证是上一交易日',
            'snapshot': {**dict(snap), 'collected_at': latest, 'freshness': freshness(snap['oldest_source_at'], target)},
            'review': (await generate_review_snapshot(target))['report'],
            'watchlist': {'items': rows, 'total': len(rows), 'quoted': matched,
                          'in_today_pool': sum(r['in_today_limit_up'] for r in rows)},
            'remote_calls': 0,
            'note': '观察池来自基准日事实，不是买入推荐；空行情不填零，历史数据不冒充实时。'}


@router.get('/history/{code}')
async def history(code: str, day: date = Query(...), limit: int = Query(60, ge=1, le=120)):
    import asyncio
    import re
    from fastapi import HTTPException
    from app.config import get_settings
    from app.services.legacy_history import read_daily
    if not re.fullmatch(r'\d{6}', code):
        raise HTTPException(422, '股票代码应为六位数字')
    return await asyncio.to_thread(read_daily, get_settings().legacy_market_db, code, day.isoformat(), limit)
