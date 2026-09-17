"""Read-only diagnostics; opening this page never consumes vendor quota."""
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Query
from sqlalchemy import text
from app.database import engine
from app.liangmai.client import liangmai
from app.services.trading_scheduler import trading_scheduler

router = APIRouter(prefix='/api/data-quality', tags=['system'])
TABLES = {
    'limit_up_pool': '涨停池', 'limit_down_pool': '跌停池',
    'dragon_tiger': '龙虎榜', 'emotion_cycle': '情绪周期',
    'capital_flow': '个股资金', 'sector_flow': '板块资金', 'market_snapshot': '行情快照',
}


async def _table_status(table, title, target):
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text(f'SELECT MAX(trade_date) FROM {table}'))
            latest = result.scalar()
            count = (await conn.execute(text(f'SELECT COUNT(*) FROM {table} WHERE trade_date=:d'), {'d': target})).scalar()
        return {'name': title, 'table': table, 'latestDate': latest, 'requestedDate': target,
                'rowCount': count, 'status': 'available' if count else 'missing', 'dataMissing': not bool(count)}
    except Exception:
        return {'name': title, 'table': table, 'requestedDate': target, 'status': 'unavailable',
                'dataMissing': True, 'msg': '数据库连接或表结构不可用'}


@router.get('/status')
async def status(date: str = Query(None, pattern=r'^\d{4}-\d{2}-\d{2}$')):
    target = date or datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()
    async def bounded(table, title):
        try:
            return await asyncio.wait_for(_table_status(table, title, target), 3)
        except asyncio.TimeoutError:
            return {'name': title, 'table': table, 'status': 'unavailable', 'dataMissing': True, 'msg': '数据库查询超时'}
    datasets = await asyncio.gather(*(bounded(t, title) for t, title in TABLES.items()))
    return {'ok': True, 'date': target, 'client': liangmai.get_status(), 'datasets': datasets,
            'scheduler': trading_scheduler.get_status(),
            'note': '有记录仅表示该日期已入库，不代表当日数据已完整或实时。'}
