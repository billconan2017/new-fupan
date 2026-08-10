"""龙虎榜 + 游资 API"""
from fastapi import APIRouter, Query
from app.services.dragon_service import (
    fetch_dragon_tiger, fetch_youzi_all, fetch_all_dragon,
    query_dragon_tiger, query_youzi_list, query_youzi_detail,
    fetch_youzi_stock, fetch_youzi_name,
)

router = APIRouter(prefix="/api/dragon", tags=["dragon"])


# ─── 查询接口 ───

@router.get("/tiger")
async def get_dragon_tiger(date: str = Query(None), limit: int = Query(50), offset: int = Query(0)):
    """获取龙虎榜（含席位明细）"""
    return await query_dragon_tiger(date, limit, offset)


@router.get("/youzi")
async def get_youzi_list(date: str = Query(None)):
    """获取游资列表（当日有操作的）"""
    return await query_youzi_list(date)


@router.get("/youzi/{youzi_id}")
async def get_youzi_detail(youzi_id: str, days: int = Query(30)):
    """获取单个游资详情及近期操作"""
    return await query_youzi_detail(youzi_id, days=days)


@router.get("/youzi/stock/{code}")
async def get_youzi_by_stock(code: str, date: str = Query(None)):
    """获取某只股票的游资操作"""
    return await fetch_youzi_stock(code, date)


@router.get("/youzi/name/{name}")
async def get_youzi_by_name(name: str, date: str = Query(None)):
    """获取指定游资的历史操作"""
    return await fetch_youzi_name(name, date)


# ─── 手动触发拉取 ───

@router.post("/fetch/tiger")
async def trigger_dragon_tiger(date: str = Query(None)):
    """手动拉取龙虎榜"""
    return await fetch_dragon_tiger(date)


@router.post("/fetch/youzi")
async def trigger_youzi(date: str = Query(None)):
    """手动拉取游资全景"""
    return await fetch_youzi_all(date)


@router.post("/fetch-all")
async def trigger_all(date: str = Query(None)):
    """手动拉取龙虎榜+游资全部"""
    return await fetch_all_dragon(date)
