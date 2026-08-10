"""健康检测 API"""
from fastapi import APIRouter
from app.liangmai.client import liangmai
from app.cache import cache

router = APIRouter(tags=["system"])


@router.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


@router.get("/health/liangmai")
async def liangmai_health():
    result = await liangmai.call("stock_list", {"dm": "000001"}, ttl=300)
    return {"ok": result["ok"], "api": "stock_list", "meta": result.get("_meta")}


@router.get("/health/redis")
async def redis_health():
    try:
        await cache.set("health_check", "ok", ttl=10)
        val = await cache.get("health_check")
        return {"ok": val == "ok"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/health/snapshot")
async def snapshot_health():
    """快照调度器状态"""
    from app.services.snapshot_scheduler import snapshot_scheduler
    return snapshot_scheduler.get_status()


@router.get("/health/full")
async def full_health():
    """完整系统健康检测"""
    from app.services.snapshot_scheduler import snapshot_scheduler

    # 量脉
    lm_result = await liangmai.call("stock_list", {"dm": "000001"}, ttl=300)
    # Redis
    redis_ok = False
    try:
        await cache.set("health_check", "ok", ttl=10)
        redis_ok = (await cache.get("health_check")) == "ok"
    except Exception:
        pass

    return {
        "service": "ok",
        "version": "1.0.0",
        "liangmai": {"ok": lm_result["ok"], "detail": liangmai.get_status()},
        "redis": {"ok": redis_ok},
        "snapshot": snapshot_scheduler.get_status(),
    }
