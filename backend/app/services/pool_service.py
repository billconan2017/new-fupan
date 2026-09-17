"""股池服务 — 涨停池/跌停池/炸板池/强势股池"""
import logging
from datetime import date, datetime
from typing import Optional
from sqlalchemy import text
from app.database import engine
from app.liangmai.client import liangmai

log = logging.getLogger("pool.service")

# 量脉池接口映射
POOL_APIS = {
    "limit_up": "stockpool_limit_up",
    "limit_down": "stockpool_limit_down",
    "broken_board": "stockpool_broken_board",
    "strong": "stockpool_strong",
}


async def fetch_pool(pool_type: str, trade_date: str = None) -> dict:
    """
    从量脉拉取股池数据并写入数据库

    Args:
        pool_type: limit_up / limit_down / broken_board / strong
        trade_date: 交易日，默认今天

    Returns:
        {"ok": bool, "count": int, "pool": str}
    """
    api = POOL_APIS.get(pool_type)
    if not api:
        return {"ok": False, "msg": f"未知池类型: {pool_type}"}

    trade_date = trade_date or date.today().isoformat()

    # 调用量脉
    result = await liangmai.call(api, params={"trade_date": trade_date}, ttl=0)
    if not result.get("ok"):
        return {"ok": False, "msg": f"量脉调用失败: {result.get('msg')}", "api": api}

    data = result.get("data")
    if not data:
        return {"ok": True, "count": 0, "pool": pool_type, "msg": "无数据"}

    # data 可能是 list 或 dict
    items = data if isinstance(data, list) else data.get("list", data.get("items", []))
    if not items:
        return {"ok": True, "count": 0, "pool": pool_type}

    # 根据池类型写入对应表
    if pool_type == "limit_up":
        count = await _insert_limit_up(trade_date, items)
    elif pool_type == "limit_down":
        count = await _insert_limit_down(trade_date, items)
    elif pool_type == "broken_board":
        count = await _insert_broken_board(trade_date, items)
    elif pool_type == "strong":
        count = await _insert_strong(trade_date, items)
    else:
        return {"ok": False, "msg": f"未实现的池类型: {pool_type}"}

    log.info(f"池 {pool_type} 写入完成: {count} 条, 日期 {trade_date}")
    return {"ok": True, "count": count, "pool": pool_type, "date": trade_date}


async def _insert_limit_up(trade_date: str, items: list) -> int:
    """写入涨停池"""
    rows = []
    for s in items:
        code = s.get("dm", s.get("c", s.get("code", "")))
        if not code:
            continue
        rows.append({
            "trade_date": trade_date,
            "code": code,
            "name": s.get("Mc", s.get("mc", s.get("n", s.get("name", "")))),
            "pct_chg": _float(s.get("zf", s.get("pc", s.get("pct_chg")))),
            "limit_type": s.get("limit_type", s.get("type", "")),
            "limit_reason": s.get("limit_reason", s.get("reason", "")),
            "first_seal_time": s.get("fbt", s.get("first_seal_time", s.get("first_time", ""))),
            "last_seal_time": s.get("lbt", s.get("last_seal_time", s.get("last_time", ""))),
            "broken_count": _int(s.get("zbc", s.get("broken_count", s.get("broken_num")))),
            "seal_amount": _float(s.get("zj", s.get("seal_amount", s.get("limit_amount")))),
            "turnover": _float(s.get("hs", s.get("turnover"))),
            "amount": _float(s.get("cje", s.get("amount"))),
            "flow_net": _float(s.get("flow_net", s.get("net_inflow"))),
            "circulating_cap": _int(s.get("lt", s.get("circulating_cap"))),
            "total_cap": _int(s.get("zsz", s.get("sz", s.get("total_cap")))),
            "industry": s.get("hy", s.get("industry", "")),
            "consecutive": _int(s.get("Lbc", s.get("lbc", s.get("consecutive", s.get("days"))))),
            "price": _float(s.get("p", s.get("price"))),
        })

    if not rows:
        return 0

    async with engine.begin() as conn:
        # 先删除当日旧数据
        await conn.execute(text("DELETE FROM limit_up_pool WHERE trade_date = :d"), {"d": trade_date})
        await conn.execute(text("""
            INSERT INTO limit_up_pool (trade_date, code, name, price, pct_chg, amount, circulating_cap,
                total_cap, turnover, first_seal_time, last_seal_time, seal_amount, consecutive,
                broken_count, industry, limit_type, limit_reason, flow_net)
            VALUES (:trade_date, :code, :name, :price, :pct_chg, :amount, :circulating_cap,
                :total_cap, :turnover, :first_seal_time, :last_seal_time, :seal_amount, :consecutive,
                :broken_count, :industry, :limit_type, :limit_reason, :flow_net)
        """), rows)
    return len(rows)


async def _insert_limit_down(trade_date: str, items: list) -> int:
    """写入跌停池"""
    rows = []
    for s in items:
        code = s.get("dm", s.get("c", s.get("code", "")))
        if not code:
            continue
        rows.append({
            "trade_date": trade_date,
            "code": code,
            "name": s.get("Mc", s.get("mc", s.get("n", s.get("name", "")))),
            "pct_chg": _float(s.get("zf", s.get("pc", s.get("pct_chg")))),
            "amount": _float(s.get("cje", s.get("amount"))),
            "turnover": _float(s.get("hs", s.get("turnover"))),
            "price": _float(s.get("p", s.get("price"))),
            "circulating_cap": _int(s.get("lt", s.get("circulating_cap"))),
            "pe": _float(s.get("pe")),
            "consecutive": _int(s.get("Lbc", s.get("lbc", s.get("consecutive", s.get("days"))))),
            "seal_amount": _float(s.get("zj", s.get("seal_amount"))),
            "board_amount": _float(s.get("fba", s.get("board_amount"))),
            "broken_count": _int(s.get("zbc", s.get("broken_count"))),
        })

    if not rows:
        return 0

    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM limit_down_pool WHERE trade_date = :d"), {"d": trade_date})
        await conn.execute(text("""
            INSERT INTO limit_down_pool (trade_date, code, name, price, pct_chg, amount, turnover,
                circulating_cap, pe, consecutive, seal_amount, board_amount, broken_count)
            VALUES (:trade_date, :code, :name, :price, :pct_chg, :amount, :turnover,
                :circulating_cap, :pe, :consecutive, :seal_amount, :board_amount, :broken_count)
        """), rows)
    return len(rows)


async def _insert_broken_board(trade_date: str, items: list) -> int:
    """写入炸板池"""
    rows = []
    for s in items:
        code = s.get("dm", s.get("c", s.get("code", "")))
        if not code:
            continue
        rows.append({
            "trade_date": trade_date,
            "code": code,
            "name": s.get("Mc", s.get("mc", s.get("n", s.get("name", "")))),
            "pct_chg": _float(s.get("zf", s.get("pc", s.get("pct_chg")))),
            "break_time": s.get("zbsj", s.get("break_time", s.get("broken_time", ""))),
            "amount": _float(s.get("cje", s.get("amount"))),
            "turnover": _float(s.get("hs", s.get("turnover"))),
            "price": _float(s.get("p", s.get("price"))),
            "broken_count": _int(s.get("zbc", s.get("broken_count", s.get("broken_num", 1)))),
            "industry": s.get("hy", s.get("industry", "")),
        })

    if not rows:
        return 0

    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM broken_board_pool WHERE trade_date = :d"), {"d": trade_date})
        await conn.execute(text("""
            INSERT INTO broken_board_pool (trade_date, code, name, price, pct_chg, amount, turnover,
                broken_count, industry, break_time)
            VALUES (:trade_date, :code, :name, :price, :pct_chg, :amount, :turnover,
                :broken_count, :industry, :break_time)
        """), rows)
    return len(rows)


async def _insert_strong(trade_date: str, items: list) -> int:
    """写入强势股池"""
    rows = []
    for s in items:
        code = s.get("dm", s.get("c", s.get("code", "")))
        if not code:
            continue
        rows.append({
            "trade_date": trade_date,
            "code": code,
            "name": s.get("Mc", s.get("mc", s.get("n", s.get("name", "")))),
            "pct_chg": _float(s.get("zf", s.get("pc", s.get("pct_chg")))),
            "continuous_days": _int(s.get("lbc", s.get("continuous_days", s.get("days")))),
            "amount": _float(s.get("cje", s.get("amount"))),
            "turnover": _float(s.get("hs", s.get("turnover"))),
            "price": _float(s.get("p", s.get("price"))),
            "volume_ratio": _float(s.get("lb", s.get("volume_ratio"))),
            "amplitude": _float(s.get("zf", s.get("amplitude"))),
            "industry": s.get("hy", s.get("industry", "")),
        })

    if not rows:
        return 0

    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM strong_pool WHERE trade_date = :d"), {"d": trade_date})
        await conn.execute(text("""
            INSERT INTO strong_pool (trade_date, code, name, price, pct_chg, amount, turnover,
                volume_ratio, amplitude, industry, continuous_days)
            VALUES (:trade_date, :code, :name, :price, :pct_chg, :amount, :turnover,
                :volume_ratio, :amplitude, :industry, :continuous_days)
        """), rows)
    return len(rows)


async def fetch_all_pools(trade_date: str = None) -> dict:
    """一次性拉取全部股池"""
    trade_date = trade_date or date.today().isoformat()
    results = {}
    for pool_type in POOL_APIS:
        results[pool_type] = await fetch_pool(pool_type, trade_date)
    return results


async def query_pool(pool_type: str, trade_date: str = None, limit: int = 100, offset: int = 0) -> dict:
    """查询股池数据"""
    trade_date = trade_date or date.today().isoformat()

    table_map = {
        "limit_up": "limit_up_pool",
        "limit_down": "limit_down_pool",
        "broken_board": "broken_board_pool",
        "strong": "strong_pool",
    }
    table = table_map.get(pool_type)
    if not table:
        return {"ok": False, "msg": f"未知池类型: {pool_type}"}

    async with engine.begin() as conn:
        result = await conn.execute(
            text(f"SELECT * FROM {table} WHERE trade_date = :d ORDER BY pct_chg DESC LIMIT :l OFFSET :o"),
            {"d": trade_date, "l": limit, "o": offset},
        )
        items = [dict(row._mapping) for row in result]

        count_result = await conn.execute(
            text(f"SELECT COUNT(*) FROM {table} WHERE trade_date = :d"),
            {"d": trade_date},
        )
        total = count_result.scalar()

    return {"ok": True, "pool": pool_type, "date": trade_date, "total": total, "items": items}


def _float(v) -> Optional[float]:
    try:
        return float(v) if v is not None else None
    except (ValueError, TypeError):
        return None


def _int(v) -> Optional[int]:
    try:
        return int(float(v)) if v is not None else None
    except (ValueError, TypeError):
        return None
