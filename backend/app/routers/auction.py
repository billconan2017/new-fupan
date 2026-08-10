"""竞价数据 API"""
from fastapi import APIRouter, Query
from app.services.auction_service import (
    fetch_auction_sectors, fetch_auction_stocks, fetch_auction_tail, fetch_auction_yizi,
    fetch_all_auction, query_auction_sectors, query_auction_stocks, query_auction_tail, query_auction_yizi,
)

router = APIRouter(prefix="/api/auction", tags=["auction"])


# ─── 查询接口 ───

@router.get("/sectors")
async def get_auction_sectors(date: str = Query(None), limit: int = Query(50)):
    """板块竞价数据"""
    return await query_auction_sectors(date, limit)


@router.get("/stocks")
async def get_auction_stocks(
    date: str = Query(None),
    limit: int = Query(50),
    offset: int = Query(0),
    min_pct: float = Query(None, description="最低涨幅过滤"),
    sort_by: str = Query("pct_chg", description="排序字段: pct_chg/amount/volume"),
):
    """个股竞价数据"""
    return await query_auction_stocks(date, limit, offset, min_pct, sort_by)


@router.get("/tail")
async def get_auction_tail(
    date: str = Query(None),
    tail_type: str = Query("wt", description="封单类型: wt/cje/close/zf"),
    limit: int = Query(30),
):
    """竞价封单排行"""
    return await query_auction_tail(date, tail_type, limit)


@router.get("/yizi")
async def get_auction_yizi(date: str = Query(None)):
    """一字涨停列表"""
    return await query_auction_yizi(date)


# ─── 手动触发拉取 ───

@router.post("/fetch/sectors")
async def trigger_sectors(date: str = Query(None)):
    return await fetch_auction_sectors(date)


@router.post("/fetch/stocks")
async def trigger_stocks(date: str = Query(None)):
    return await fetch_auction_stocks(date)


@router.post("/fetch/tail")
async def trigger_tail(date: str = Query(None)):
    return await fetch_auction_tail(date)


@router.post("/fetch/yizi")
async def trigger_yizi(date: str = Query(None)):
    return await fetch_auction_yizi(date)


@router.post("/fetch-all")
async def trigger_all(date: str = Query(None)):
    """拉取全部竞价数据"""
    return await fetch_all_auction(date)
