"""板块热力图 + 轮动 API"""
from fastapi import APIRouter, Query
from app.services.sector_service import (
    fetch_sector_heatmap, query_sector_rotation,
    fetch_sector_tree, fetch_sector_stocks, fetch_sector_auction,
)

router = APIRouter(prefix="/api/sector", tags=["sector"])


# ─── 查询接口 ───

@router.get("/heatmap")
async def get_heatmap(date: str = Query(None)):
    """板块热力图（涨跌 + 资金流）"""
    return await fetch_sector_heatmap(date)


@router.get("/rotation")
async def get_rotation(days: int = Query(5), top_n: int = Query(20)):
    """板块轮动分析（近 N 天涨跌 + 趋势）"""
    return await query_sector_rotation(days, top_n)


@router.get("/tree")
async def get_tree():
    """板块树形结构（行业 + 概念）"""
    return await fetch_sector_tree()


@router.get("/stocks/{sector_code}")
async def get_sector_stocks(sector_code: str):
    """板块成分股"""
    return await fetch_sector_stocks(sector_code)


@router.get("/auction")
async def get_sector_auction(date: str = Query(None)):
    """板块竞价热度"""
    return await fetch_sector_auction(date)
