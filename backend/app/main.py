from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.cache import cache
from app.liangmai.client import liangmai
from app.routers import health, snapshot, fupan, auction, sector, finance, kline, dragon, pools, emotion, capital, review, scheduler, strategy, trading
import logging

settings = get_settings()
log = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        from app.database import init_db
        await init_db()
        log.info("PostgreSQL connected")
    except Exception as e:
        log.warning(f"PostgreSQL unavailable: {e}")
    try:
        await cache.connect()
        log.info("Redis connected")
    except Exception as e:
        log.warning(f"Redis unavailable: {e}")
    await liangmai.connect()
    log.info("Liangmai client ready")
    try:
        from app.services.snapshot_scheduler import snapshot_scheduler
        if settings.scheduler_enabled:
            await snapshot_scheduler.start()
        log.info("Snapshot scheduler started")
    except Exception as e:
        log.warning(f"Snapshot scheduler failed: {e}")
    # 启动交易调度器 (APScheduler)
    try:
        from app.services.trading_scheduler import trading_scheduler
        if settings.scheduler_enabled:
            trading_scheduler.start()
        log.info("Trading scheduler started")
    except Exception as e:
        log.warning(f"Trading scheduler failed: {e}")

    # 保留旧调度器兼容（已禁用，由 trading_scheduler 接管）
    # try:
    #     from app.services.batch_fetch_scheduler import batch_scheduler
    #     await batch_scheduler.start()
    #     log.info("Batch fetch scheduler started")
    # except Exception as e:
    #     log.warning(f"Batch fetch scheduler failed: {e}")
    yield
    try:
        from app.services.snapshot_scheduler import snapshot_scheduler
        await snapshot_scheduler.stop()
    except Exception:
        pass
    try:
        from app.services.trading_scheduler import trading_scheduler
        trading_scheduler.stop()
    except Exception:
        pass
    # try:
    #     from app.services.batch_fetch_scheduler import batch_scheduler
    #     await batch_scheduler.stop()
    # except Exception:
    #     pass
    await liangmai.close()
    await cache.disconnect()


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
from app.routers import data_quality, cockpit
app.include_router(cockpit.router)
app.include_router(data_quality.router)
app.include_router(snapshot.router)
app.include_router(fupan.router)
app.include_router(auction.router)
app.include_router(sector.router)
app.include_router(finance.router)
app.include_router(kline.router)
app.include_router(dragon.router)
app.include_router(pools.router)
app.include_router(emotion.router)
app.include_router(capital.router)
app.include_router(review.router)
app.include_router(scheduler.router)
app.include_router(strategy.router)
app.include_router(trading.router)


from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.requests import Request
from starlette.responses import Response

_project_root = Path(__file__).resolve().parent.parent.parent
_dist = _project_root / "dist"
if not (_dist / "index.html").exists():
    _dist = _project_root / "frontend" / "dist"


@app.get("/")
async def root():
    if (_dist / "index.html").exists():
        return FileResponse(_dist / "index.html")
    return {"app": settings.app_name, "version": settings.app_version}


if _dist.exists():
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.exception_handler(404)
    async def spa_fallback(request: Request, exc):
        """SPA 路由回退: 非 API 的 404 返回 index.html"""
        path = request.url.path
        if path.startswith("/api/"):
            return Response(content='{"detail":"Not Found"}', status_code=404, media_type="application/json")
        file_path = _dist / path.lstrip("/")
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(_dist / "index.html")
