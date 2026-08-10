"""股池 API — 涨停池/跌停池/炸板池/强势股池"""
from fastapi import APIRouter, Query
from app.services.pool_service import fetch_pool, fetch_all_pools, query_pool

router = APIRouter(prefix="/api/pools", tags=["pools"])


@router.get("/limit-up")
async def get_limit_up(date: str = Query(None), limit: int = Query(100), offset: int = Query(0)):
    """获取涨停池"""
    return await query_pool("limit_up", date, limit, offset)


@router.get("/limit-down")
async def get_limit_down(date: str = Query(None), limit: int = Query(100), offset: int = Query(0)):
    """获取跌停池"""
    return await query_pool("limit_down", date, limit, offset)


@router.get("/broken-board")
async def get_broken_board(date: str = Query(None), limit: int = Query(100), offset: int = Query(0)):
    """获取炸板池"""
    return await query_pool("broken_board", date, limit, offset)


@router.get("/strong")
async def get_strong(date: str = Query(None), limit: int = Query(100), offset: int = Query(0)):
    """获取强势股池"""
    return await query_pool("strong", date, limit, offset)


@router.post("/fetch/{pool_type}")
async def trigger_fetch(pool_type: str, date: str = Query(None)):
    """手动触发拉取指定股池"""
    return await fetch_pool(pool_type, date)


@router.post("/fetch-all")
async def trigger_fetch_all(date: str = Query(None)):
    """手动触发拉取全部股池"""
    return await fetch_all_pools(date)
