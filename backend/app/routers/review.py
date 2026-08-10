"""盘后复盘报告 API"""
from fastapi import APIRouter, Query
from app.services.review_service import (
    generate_review, generate_review_snapshot, query_review, query_review_list,
)

router = APIRouter(prefix="/api/review", tags=["review"])


@router.get("/report")
async def get_review(date: str = Query(None)):
    """查询指定日期复盘报告"""
    return await query_review(date)


@router.get("/list")
async def get_review_list(limit: int = Query(30), offset: int = Query(0)):
    """复盘报告列表（分页）"""
    return await query_review_list(limit, offset)


@router.post("/generate")
async def trigger_generate(date: str = Query(None)):
    """生成盘后复盘报告（写入数据库）"""
    return await generate_review(date)


@router.get("/snapshot")
async def get_snapshot(date: str = Query(None)):
    """预览复盘报告（不写库）"""
    return await generate_review_snapshot(date)
