"""情绪周期 API"""
from fastapi import APIRouter, Query
from app.services.emotion_service import fetch_emotion_cycle, query_emotion, query_emotion_summary

router = APIRouter(prefix="/api/emotion", tags=["emotion"])


@router.get("/cycle")
async def get_emotion_cycle(date: str = Query(None), days: int = Query(30)):
    """情绪周期（当日 + 趋势）"""
    return await query_emotion(date, days)


@router.get("/summary")
async def get_emotion_summary(date: str = Query(None)):
    """情绪摘要：状态/连续天数/风险等级"""
    return await query_emotion_summary(date)


@router.post("/fetch")
async def trigger_emotion(date: str = Query(None)):
    """手动拉取情绪周期"""
    return await fetch_emotion_cycle(date)
