from datetime import date
from fastapi import APIRouter, Query
from sqlalchemy import text
from app.liangmai.client import liangmai
from app.database import engine
from app.cache import cache

router = APIRouter(prefix="/api/kline", tags=["kline"])

VALID_INTERVALS = {"day", "1", "5", "10", "15", "30", "60"}


async def _query_local_kline(code: str, interval: str, limit: int) -> list | None:
    """从本地PG查询K线数据，返回None表示无数据"""
    code6 = code.split(".")[0] if "." in code else code
    async with engine.begin() as conn:
        if interval == "day":
            result = await conn.execute(text(
                "SELECT code, trade_date as time, open, high, low, close, volume, amount, pct_chg "
                "FROM stock_daily_kline WHERE code = :code ORDER BY trade_date DESC LIMIT :limit"
            ), {"code": code6, "limit": limit})
        else:
            period = int(interval)
            result = await conn.execute(text(
                "SELECT code, trade_date, time, open, high, low, close, volume, amount, avg "
                "FROM stock_minute_kline WHERE code = :code AND period = :period "
                "ORDER BY trade_date DESC, time DESC LIMIT :limit"
            ), {"code": code6, "period": period, "limit": limit})

        rows = [dict(r._mapping) for r in result]
        if not rows:
            return None
        # 反转为时间正序
        rows.reverse()
        return rows


async def _fetch_and_persist(code: str, interval: str, limit: int) -> dict:
    """从量脉拉取K线并持久化入库"""
    code6 = code.split(".")[0] if "." in code else code
    
    # 构造 full_code
    if code6.startswith("6"):
        full_code = f"{code6}.SH"
    elif code6.startswith(("0", "3")):
        full_code = f"{code6}.SZ"
    elif code6.startswith(("4", "8")):
        full_code = f"{code6}.BJ"
    else:
        full_code = code6

    params = {"full_code": full_code, "interval": interval, "lt": str(limit)}
    result = await liangmai.call("quote_bars_history", params, ttl=300)

    if not result.get("ok"):
        return result

    data = result.get("data", [])
    if isinstance(data, dict):
        data = data.get("list", data.get("items", data.get("candles", [])))
    if not isinstance(data, list) or not data:
        return result

    # 入库
    try:
        async with engine.begin() as conn:
            for item in data:
                time_str = str(item.get("time", item.get("dt", item.get("date", ""))))
                if not time_str:
                    continue

                if interval == "day":
                    await conn.execute(text("""
                        INSERT INTO stock_daily_kline (code, trade_date, open, high, low, close, volume, amount, pct_chg, source, updated_at)
                        VALUES (:code, :td, :o, :h, :l, :c, :v, :a, :pct, 'liangmai', NOW())
                        ON CONFLICT (code, trade_date) DO UPDATE SET
                            open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low, close=EXCLUDED.close,
                            volume=EXCLUDED.volume, amount=EXCLUDED.amount, pct_chg=EXCLUDED.pct_chg,
                            source='liangmai', updated_at=NOW()
                    """), {
                        "code": code6, "td": time_str[:10],
                        "o": _f(item, "open", "o"), "h": _f(item, "high", "h"),
                        "l": _f(item, "low", "l"), "c": _f(item, "close", "c"),
                        "v": _f(item, "volume", "vol", "v"), "a": _f(item, "amount", "a", "turnover"),
                        "pct": _f(item, "pct_chg", "change_pct"),
                    })
                else:
                    period = int(interval)
                    # 提取trade_date: 从time_str中取日期部分
                    td = time_str[:10] if len(time_str) >= 10 else time_str
                    await conn.execute(text("""
                        INSERT INTO stock_minute_kline (code, trade_date, time, period, open, high, low, close, volume, amount, avg, source, updated_at)
                        VALUES (:code, :td, :tm, :p, :o, :h, :l, :c, :v, :a, :avg, 'liangmai', NOW())
                        ON CONFLICT (code, trade_date, time, period) DO UPDATE SET
                            open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low, close=EXCLUDED.close,
                            volume=EXCLUDED.volume, amount=EXCLUDED.amount, avg=EXCLUDED.avg,
                            source='liangmai', updated_at=NOW()
                    """), {
                        "code": code6, "td": td, "tm": time_str, "p": period,
                        "o": _f(item, "open", "o"), "h": _f(item, "high", "h"),
                        "l": _f(item, "low", "l"), "c": _f(item, "close", "c"),
                        "v": _f(item, "volume", "vol", "v"), "a": _f(item, "amount", "a", "turnover"),
                        "avg": _f(item, "avg", "average", "wap"),
                    })
    except Exception as e:
        # 入库失败不影响返回
        import logging
        logging.getLogger("kline").warning(f"K线入库失败 {code6} {interval}: {e}")

    return result


def _f(item: dict, *keys) -> float:
    for k in keys:
        v = item.get(k)
        if v is not None:
            try:
                return float(v)
            except (ValueError, TypeError):
                pass
    return 0.0


@router.get("/daily/{code}")
async def daily_kline(code: str, start: str = "", end: str = "", limit: int = 120):
    """日K线 — 本地PG优先，无数据调用量脉拉取入库"""
    local = await _query_local_kline(code, "day", limit)
    if local is not None:
        return {"ok": True, "data": local, "source": "local"}
    return await _fetch_and_persist(code, "day", limit)


@router.get("/minute/{code}")
async def minute_kline(code: str, interval: int = 5, limit: int = 48):
    """分钟K线 — 本地PG优先，无数据调用量脉拉取入库
    
    interval: 5/10/15/30/60
    """
    interval_str = str(interval)
    if interval_str not in VALID_INTERVALS:
        return {"ok": False, "msg": f"无效周期: {interval}, 有效: {VALID_INTERVALS}"}

    local = await _query_local_kline(code, interval_str, limit)
    if local is not None:
        return {"ok": True, "data": local, "source": "local"}
    return await _fetch_and_persist(code, interval_str, limit)


@router.get("/latest/{code}")
async def latest_kline(code: str, interval: int = 5):
    """最新K线"""
    result = await liangmai.call(
        "quote_bars_latest",
        {"full_code": code, "interval": str(interval)},
        ttl=5,
    )
    return result


@router.get("/tech/{code}")
async def tech_indicators(code: str, indicator: str = "macd"):
    """技术指标 (macd/ma/boll/kdj)"""
    api_map = {
        "macd": "tech_macd",
        "ma": "tech_ma",
        "boll": "tech_boll",
        "kdj": "tech_kdj",
    }
    api = api_map.get(indicator, "tech_macd")
    result = await liangmai.call(api, {"ts_code": code}, ttl=300)
    return result


@router.get("/periods")
async def available_periods():
    """返回支持的K线周期列表"""
    return {
        "ok": True,
        "periods": [
            {"value": "day", "label": "日K", "interval": "day"},
            {"value": "60", "label": "60分钟", "interval": 60},
            {"value": "30", "label": "30分钟", "interval": 30},
            {"value": "15", "label": "15分钟", "interval": 15},
            {"value": "10", "label": "10分钟", "interval": 10},
            {"value": "5", "label": "5分钟", "interval": 5},
            {"value": "1", "label": "1分钟", "interval": 1},
        ],
    }
