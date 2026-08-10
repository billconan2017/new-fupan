"""资金流向 API"""
from fastapi import APIRouter, Query
from app.services.capital_service import (
    fetch_capital_flow, fetch_sector_flow, fetch_all_capital,
    query_capital_flow, query_sector_flow, query_capital_detail,
)

router = APIRouter(prefix="/api/capital", tags=["capital"])


# ─── 查询接口 ───

@router.get("/flow")
async def get_capital_flow(
    date: str = Query(None),
    limit: int = Query(50),
    offset: int = Query(0),
    sort_by: str = Query("main_net", description="排序: main_net/super_large_net/large_net/main_pct"),
    direction: str = Query("desc", description="asc/desc"),
):
    """个股资金流向排行"""
    return await query_capital_flow(date, limit, offset, sort_by, direction)


@router.get("/sectors")
async def get_sector_flow(
    date: str = Query(None),
    limit: int = Query(30),
    sort_by: str = Query("main_net", description="排序: main_net/total_net/change_pct"),
):
    """板块资金流向"""
    return await query_sector_flow(date, limit, sort_by)


@router.get("/stock/{code}")
async def get_capital_detail(code: str, days: int = Query(10)):
    """个股资金流历史"""
    return await query_capital_detail(code, days)


# ─── 手动触发拉取 ───

@router.post("/fetch/stock")
async def trigger_stock_flow(date: str = Query(None)):
    """拉取个股资金流（涨停池+龙虎榜标的）"""
    return await fetch_capital_flow(date)


@router.post("/fetch/sector")
async def trigger_sector_flow(date: str = Query(None)):
    """拉取板块资金流"""
    return await fetch_sector_flow(date)


@router.post("/fetch-all")
async def trigger_all(date: str = Query(None)):
    """拉取全部资金流"""
    return await fetch_all_capital(date)
