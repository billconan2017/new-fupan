"""调度器管理 API — 状态查询 + 手动触发 + 历史回填"""
from fastapi import APIRouter, Query
from app.services.trading_scheduler import trading_scheduler

router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])


@router.get("/status")
async def get_scheduler_status():
    """查询调度器状态"""
    return {"ok": True, "scheduler": trading_scheduler.get_status()}


@router.post("/trigger/post-market")
async def trigger_post_market(date: str = Query(None)):
    """手动触发盘后全量拉取"""
    return await trading_scheduler.trigger_post_market(date)


@router.post("/backfill")
async def trigger_backfill(
    start_date: str = Query(..., description="起始日期 YYYY-MM-DD"),
    end_date: str = Query(None, description="结束日期 YYYY-MM-DD (默认同一天)"),
):
    """历史回填：批量拉取指定日期范围的数据"""
    return await trading_scheduler.backfill(start_date, end_date)


@router.post("/fetch-all")
async def fetch_all_for_date(date: str = Query(..., description="日期 YYYY-MM-DD")):
    """单日全量拉取"""
    return await trading_scheduler.trigger_fetch_all(date)
