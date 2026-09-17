from fastapi import APIRouter
from app.liangmai.client import liangmai
from app.liangmai.parsing import emotion_for_date

router = APIRouter(prefix="/api/fupan", tags=["fupan"])


@router.get("/limit-up/{date}")
async def limit_up(date: str):
    """涨停池"""
    result = await liangmai.call("stockpool_limit_up", {"trade_date": date}, ttl=300)
    return result


@router.get("/limit-down/{date}")
async def limit_down(date: str):
    """跌停池"""
    result = await liangmai.call("pool_limit_down", {"trade_date": date}, ttl=300)
    return result


@router.get("/strong/{date}")
async def strong(date: str):
    """强势股池"""
    result = await liangmai.call("pool_strong", {"trade_date": date}, ttl=300)
    return result


@router.get("/broken-board/{date}")
async def broken_board(date: str):
    """炸板池"""
    result = await liangmai.call("pool_broken_board", {"trade_date": date}, ttl=300)
    return result


@router.get("/emotion/{date}")
async def emotion(date: str):
    """情绪周期"""
    result = await liangmai.call("anomaly_emotion_cycle", ttl=300)
    if result.get("ok"):
        row = emotion_for_date(result.get("data"), date)
        result["data"] = row
        result["_meta"]["dataMissing"] = row is None
        result["_meta"]["dataDate"] = date if row else None
        result["msg"] = "ok" if row else "请求日期无情绪数据"
    return result


@router.get("/dragon-tiger/{date}")
async def dragon_tiger(date: str):
    """龙虎榜"""
    result = await liangmai.call("lhb_daily", {"date": date}, ttl=300)
    return result
