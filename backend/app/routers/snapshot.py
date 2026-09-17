"""快照查询 API"""
from fastapi import APIRouter, Query
from sqlalchemy import text
from app.database import engine
from app.services.snapshot_scheduler import snapshot_scheduler

router = APIRouter(tags=["snapshot"])


@router.get("/snapshot/status")
async def snapshot_status():
    """快照调度器状态"""
    return snapshot_scheduler.get_status()


@router.get("/snapshot/latest")
async def snapshot_latest(
    sort_by: str = Query("pct_chg", description="排序字段"),
    sort_order: str = Query("desc", description="asc/desc"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """获取最新一次全市场快照"""
    async with engine.begin() as conn:
        # 获取最新快照时间
        row = await conn.execute(
            text("SELECT trade_date, snapshot_at FROM market_snapshot ORDER BY snapshot_at DESC LIMIT 1")
        )
        latest = row.first()
        if not latest:
            return {"snapshot_time": None, "total": 0, "items": []}

        # 查询数据
        allowed_sorts = {"pct_chg", "amount", "turnover", "volume_ratio", "amplitude", "price"}
        sort_field = sort_by if sort_by in allowed_sorts else "pct_chg"
        direction = "DESC" if sort_order == "desc" else "ASC"

        result = await conn.execute(
            text(f"""
                SELECT code, name, price, pct_chg, amount, volume, open, high, low,
                       pre_close, turnover, volume_ratio, amplitude, circulating_cap, total_cap
                FROM market_snapshot
                WHERE trade_date = :trade_date AND snapshot_at = :snapshot_at
                ORDER BY {sort_field} {direction} NULLS LAST
                LIMIT :limit OFFSET :offset
            """),
            {"trade_date": latest[0], "snapshot_at": latest[1], "limit": limit, "offset": offset},
        )
        items = [dict(row._mapping) for row in result]

        # 总数
        count_row = await conn.execute(
            text("SELECT COUNT(*) FROM market_snapshot WHERE trade_date = :d AND snapshot_at = :s"),
            {"d": latest[0], "s": latest[1]},
        )
        total = count_row.scalar()

    return {
        "snapshot_time": latest[1],
        "trade_date": latest[0],
        "total": total,
        "items": items,
    }


@router.post("/api/snapshot/fetch")
@router.post("/snapshot/fetch")
async def snapshot_fetch():
    """手动触发快照拉取（测试用）"""
    from app.services.snapshot_scheduler import snapshot_scheduler
    result = await snapshot_scheduler._fetch_and_store()
    return {**result, **snapshot_scheduler.get_status()}


@router.get("/snapshot/stats")
async def snapshot_stats():
    """涨跌统计 / 板块聚合"""
    async with engine.begin() as conn:
        row = await conn.execute(
            text("SELECT trade_date, snapshot_at FROM market_snapshot ORDER BY snapshot_at DESC LIMIT 1")
        )
        latest = row.first()
        if not latest:
            return {"data": None}

        d, s = latest[0], latest[1]

        # 涨跌统计
        stats = await conn.execute(text(f"""
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE pct_chg > 0) as rise_count,
                COUNT(*) FILTER (WHERE pct_chg < 0) as fall_count,
                COUNT(*) FILTER (WHERE pct_chg = 0) as flat_count,
                COUNT(*) FILTER (WHERE pct_chg >= 9.9) as limit_up,
                COUNT(*) FILTER (WHERE pct_chg <= -9.9) as limit_down,
                ROUND(AVG(pct_chg)::numeric, 2) as avg_pct,
                SUM(amount) as total_amount
            FROM market_snapshot
            WHERE trade_date = '{d}' AND snapshot_at = '{s}'
        """))
        stat = dict(stats.first()._mapping)

    return {"trade_date": d, "snapshot_time": s, **stat}


@router.get("/snapshot/stock/{code}")
async def snapshot_stock(code: str, date: str = Query(None)):
    """获取个股当日快照序列"""
    async with engine.begin() as conn:
        if date:
            result = await conn.execute(
                text("SELECT * FROM market_snapshot WHERE code = :code AND trade_date = :d ORDER BY snapshot_at"),
                {"code": code, "d": date},
            )
        else:
            result = await conn.execute(
                text("SELECT * FROM market_snapshot WHERE code = :code ORDER BY snapshot_at DESC LIMIT 240"),
                {"code": code},
            )
        items = [dict(row._mapping) for row in result]
    return {"code": code, "count": len(items), "items": items}
