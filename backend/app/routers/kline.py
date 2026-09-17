from datetime import date
from fastapi import APIRouter, Query, HTTPException
import logging
from app.liangmai.parsing import number, source_date
from sqlalchemy import text
from app.liangmai.client import liangmai
from app.database import engine
from app.cache import cache

router = APIRouter(prefix="/api/kline", tags=["kline"])

VALID_INTERVALS = {"day", "1", "5", "15", "30", "60"}


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


async def _fetch_and_persist(code: str, interval: str, limit: int, start: str = "", end: str = "") -> dict:
    """从量脉拉取K线并持久化入库"""
    code6 = code.split(".")[0] if "." in code else code
    
    # 构造 full_code
    if code6.startswith("6"):
        full_code = f"{code6}.SH"
    elif code6.startswith(("0", "3")):
        full_code = f"{code6}.SZ"
    elif code6.startswith(("4", "8", "9")):
        full_code = f"{code6}.BJ"
    else:
        full_code = code6

    params = {"full_code": full_code, "interval": "d" if interval == "day" else interval, "lt": limit, "cq": "n"}
    if start:
        params["st"] = start.replace("-", "")
    if end:
        params["et"] = end.replace("-", "")
    result = await liangmai.call("kline_history", params, ttl=60)

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
                time_str = str(item.get("t", item.get("time", item.get("dt", item.get("date", "")))))
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
                        "code": code6, "td": source_date(time_str),
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
    return None


async def _load(code, interval, limit, start="", end=""):
    result = await _fetch_and_persist(code, interval, limit, start, end)
    if result.get("ok") or result.get("code") == "invalid_request":
        if result.get("ok"):
            data = result.get("data")
            if isinstance(data, dict):
                data = data.get("list", data.get("items", []))
            result["data"] = [normalize_bar(x) for x in (data or []) if isinstance(x, dict)]
            result["source"] = "liangmai"
        return result
    try:
        local = await _query_local_kline(code, interval, limit)
    except Exception:
        local = None
    if local:
        local = [r for r in local if (not start or str(r["time"])[:10].replace("-", "") >= start.replace("-", ""))
                 and (not end or str(r["time"])[:10].replace("-", "") <= end.replace("-", ""))]
    if local:
        return {"ok": True, "data": local, "source": "local",
                "msg": "上游不可用，展示本地历史数据", "_meta": {
                    "stale": True, "dataMissing": True, "fallbackReason": result.get("code"),
                    "dataDate": str(local[-1]["time"])[:10]}}
    return result


def normalize_bar(item):
    return {**item, "time": item.get("t", item.get("time")),
            "open": _f(item, "o", "open"), "high": _f(item, "h", "high"),
            "low": _f(item, "l", "low"), "close": _f(item, "c", "close"),
            "volume": _f(item, "v", "volume"), "amount": _f(item, "a", "amount")}


@router.get("/daily/{code}")
async def daily_kline(code: str, start: str = "", end: str = "", limit: int = Query(120, ge=1, le=5000)):
    return await _load(code, "day", limit, start, end)


@router.get("/minute/{code}")
async def minute_kline(code: str, interval: int = 5, limit: int = Query(48, ge=1, le=5000)):
    if str(interval) not in VALID_INTERVALS:
        raise HTTPException(422, "支持的分钟周期为 1/5/15/30/60")
    return await _load(code, str(interval), limit)


@router.get("/latest/{code}")
async def latest_kline(code: str, interval: int = 5):
    """最新K线"""
    result = await liangmai.call(
        "kline_latest",
        {"full_code": code, "interval": str(interval)},
        ttl=5,
    )
    return result


@router.get("/tech/{code}")
async def tech_indicators(code: str, indicator: str = "macd"):
    """技术指标 (macd/ma/boll/kdj)"""
    api_map = {
        "macd": "indicator_macd",
        "ma": "indicator_ma",
        "boll": "indicator_boll",
        "kdj": "indicator_kdj",
    }
    api = api_map.get(indicator, "indicator_macd")
    result = await liangmai.call(api, {"full_code": code}, ttl=300)
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
            {"value": "5", "label": "5分钟", "interval": 5},
            {"value": "1", "label": "1分钟", "interval": 1},
        ],
    }
