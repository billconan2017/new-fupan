"""策略选股 API"""
from fastapi import APIRouter, Query, Body
from app.services.strategy_service import (
    screen_stocks, save_strategy, get_strategies, get_strategy_detail,
    delete_strategy, backtest_strategy, export_stocks,
)

router = APIRouter(prefix="/api/strategy", tags=["strategy"])


@router.post("/screen")
async def api_screen(filters: dict = Body(...), date: str = Query(None)):
    """多条件筛选选股"""
    return await screen_stocks(filters, date)


@router.post("/save")
async def api_save(
    name: str = Query(...),
    filters: dict = Body(...),
    date: str = Query(None),
    results: list = Body(default=[]),
):
    """保存选股方案"""
    return await save_strategy(name, filters, date, results)


@router.get("/list")
async def api_list(name: str = Query(None), limit: int = Query(50)):
    """读取方案列表"""
    return await get_strategies(name, limit)


@router.get("/detail/{strategy_id}")
async def api_detail(strategy_id: int):
    """方案详情"""
    return await get_strategy_detail(strategy_id)


@router.delete("/{strategy_id}")
async def api_delete(strategy_id: int):
    """删除方案"""
    return await delete_strategy(strategy_id)


@router.post("/backtest")
async def api_backtest(
    filters: dict = Body(...),
    start_date: str = Query(...),
    end_date: str = Query(None),
):
    """历史回测"""
    return await backtest_strategy(filters, start_date, end_date)


@router.post("/export")
async def api_export(filters: dict = Body(...), date: str = Query(None)):
    """导出选股结果"""
    return await export_stocks(filters, date)
