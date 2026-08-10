"""资金流向服务 — 个股资金流 + 板块资金流"""
import logging
from datetime import date
from typing import Optional
from sqlalchemy import text
from app.database import engine
from app.liangmai.client import liangmai

log = logging.getLogger("capital.service")


# ───────────────── 个股资金流向 ─────────────────

async def fetch_capital_flow(trade_date: str = None) -> dict:
    """拉取涨跌停股 + 自选股的资金流向写入 capital_flow

    注：个股资金流无全市场批量接口，需逐只调用。策略：
    1. 从当日涨停池取前 50 只
    2. 从当日龙虎榜取全部
    3. 合并去重后批量拉取资金流
    """
    trade_date = trade_date or date.today().isoformat()

    # 收集目标股票
    target_codes = set()
    async with engine.begin() as conn:
        # 涨停池
        result = await conn.execute(text(
            "SELECT code FROM limit_up_pool WHERE trade_date = :d LIMIT 50"), {"d": trade_date})
        for row in result:
            target_codes.add(row[0])

        # 龙虎榜
        result = await conn.execute(text(
            "SELECT code FROM dragon_tiger WHERE trade_date = :d"), {"d": trade_date})
        for row in result:
            target_codes.add(row[0])

    if not target_codes:
        return {"ok": True, "count": 0, "msg": "无目标股票（需先拉取涨停池/龙虎榜）"}

    # 批量拉取资金流
    rows = []
    failed = 0
    for code in target_codes:
        result = await liangmai.call("base_code_flow", params={"ts_code": code}, ttl=300)
        if not result.get("ok"):
            failed += 1
            continue
        data = result.get("data")
        if not data:
            continue
        # data 可能是 list 或 dict
        items = data if isinstance(data, list) else [data]
        for item in items:
            rows.append({
                "trade_date": trade_date,
                "code": code,
                "name": item.get("name", item.get("n", "")),
                "main_net": _int(item.get("main_net", item.get("mainNet", item.get("zljlr", 0)))),
                "super_large_net": _int(item.get("super_large_net", item.get("superLargeNet", item.get("cddlr", 0)))),
                "large_net": _int(item.get("large_net", item.get("largeNet", item.get("ddlr", 0)))),
                "medium_net": _int(item.get("medium_net", item.get("mediumNet", item.get("zdlr", 0)))),
                "small_net": _int(item.get("small_net", item.get("smallNet", item.get("xdlr", 0)))),
                "main_pct": _float(item.get("main_pct", item.get("mainPct", 0))),
            })

    if not rows:
        return {"ok": True, "count": 0, "failed": failed, "msg": "无资金流数据"}

    # 写入数据库
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM capital_flow WHERE trade_date = :d"), {"d": trade_date})
        await conn.execute(text("""
            INSERT INTO capital_flow (trade_date, code, name, main_net, super_large_net, large_net, medium_net, small_net, main_pct)
            VALUES (:trade_date, :code, :name, :main_net, :super_large_net, :large_net, :medium_net, :small_net, :main_pct)
        """), rows)

    log.info(f"个股资金流写入: {len(rows)} 条, 失败 {failed}")
    return {"ok": True, "count": len(rows), "failed": failed, "date": trade_date}


# ───────────────── 板块资金流向 ─────────────────

async def fetch_sector_flow(trade_date: str = None) -> dict:
    """拉取板块资金流向 → sector_flow

    修复：自动从 sector_tree 表读取合法 bkCode 列表，
    补齐必填入参，根除 422 参数缺失报错。
    """
    trade_date = trade_date or date.today().isoformat()

    # 先从 sector_tree 读取合法板块代码
    bk_codes = []
    try:
        async with engine.begin() as conn:
            result = await conn.execute(text(
                "SELECT sector_code FROM sector_tree WHERE source IN ('881','884') LIMIT 200"))
            bk_codes = [row[0] for row in result]
    except Exception:
        pass

    # 调用量脉，带上合法 bkCode 参数
    params = {"tradeDate": trade_date}
    if bk_codes:
        params["bkCodes"] = "|".join(bk_codes[:50])  # 批量传码，防止 422

    result = await liangmai.call("base_bk_flow_history", params=params, ttl=0)
    if not result.get("ok"):
        # 尝试备选接口
        result = await liangmai.call("board_flow_history", params={"date": trade_date}, ttl=0)
    if not result.get("ok"):
        return {"ok": False, "msg": f"量脉调用失败: {result.get('msg')}"}

    data = result.get("data")
    if not data:
        return {"ok": True, "count": 0, "msg": "无板块资金流数据"}

    items = data if isinstance(data, list) else data.get("list", data.get("items", []))
    if not items:
        return {"ok": True, "count": 0}

    rows = []
    for s in items:
        code = s.get("bkCode", s.get("code", s.get("sector_code", "")))
        if not code:
            continue
        rows.append({
            "trade_date": trade_date,
            "sector_code": code,
            "sector_name": s.get("bkName", s.get("name", s.get("sector_name", ""))),
            "main_net": _int(s.get("mainNet", s.get("main_net", s.get("zljlr", 0)))),
            "retail_net": _int(s.get("retailNet", s.get("retail_net", s.get("shlr", 0)))),
            "total_net": _int(s.get("totalNet", s.get("total_net", s.get("net_inflow", 0)))),
            "change_pct": _float(s.get("changePct", s.get("change_pct", s.get("zf", 0)))),
            "rise_count": _int(s.get("riseCount", s.get("rise_count", s.get("upNum", 0)))),
            "fall_count": _int(s.get("fallCount", s.get("fall_count", s.get("downNum", 0)))),
            "leader_code": s.get("leaderCode", s.get("leader_code", s.get("topCode", ""))),
            "leader_name": s.get("leaderName", s.get("leader_name", s.get("topName", ""))),
            "leader_pct": _float(s.get("leaderPct", s.get("leader_pct", s.get("topPct", 0)))),
        })

    if not rows:
        return {"ok": True, "count": 0}

    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM sector_flow WHERE trade_date = :d"), {"d": trade_date})
        await conn.execute(text("""
            INSERT INTO sector_flow (trade_date, sector_code, sector_name, main_net, retail_net, total_net,
                change_pct, rise_count, fall_count, leader_code, leader_name, leader_pct)
            VALUES (:trade_date, :sector_code, :sector_name, :main_net, :retail_net, :total_net,
                :change_pct, :rise_count, :fall_count, :leader_code, :leader_name, :leader_pct)
        """), rows)

    log.info(f"板块资金流写入: {len(rows)} 条")
    return {"ok": True, "count": len(rows), "date": trade_date}


async def fetch_all_capital(trade_date: str = None) -> dict:
    """一次性拉取个股 + 板块资金流"""
    trade_date = trade_date or date.today().isoformat()
    stock = await fetch_capital_flow(trade_date)
    sector = await fetch_sector_flow(trade_date)
    return {"stock_flow": stock, "sector_flow": sector}


# ───────────────── 查询接口 ─────────────────

async def query_capital_flow(trade_date: str = None, limit: int = 50, offset: int = 0,
                              sort_by: str = "main_net", direction: str = "desc") -> dict:
    """查询个股资金流向排行"""
    trade_date = trade_date or date.today().isoformat()
    allowed_sorts = {"main_net", "super_large_net", "large_net", "medium_net", "small_net", "main_pct"}
    sort_field = sort_by if sort_by in allowed_sorts else "main_net"
    order = "DESC" if direction == "desc" else "ASC"

    async with engine.begin() as conn:
        result = await conn.execute(text(f"""
            SELECT * FROM capital_flow WHERE trade_date = :d
            ORDER BY {sort_field} {order} NULLS LAST LIMIT :l OFFSET :o
        """), {"d": trade_date, "l": limit, "o": offset})
        items = [dict(row._mapping) for row in result]

        total_result = await conn.execute(
            text("SELECT COUNT(*) FROM capital_flow WHERE trade_date = :d"), {"d": trade_date})
        total = total_result.scalar()

    return {"ok": True, "date": trade_date, "total": total, "items": items}


async def query_sector_flow(trade_date: str = None, limit: int = 30, sort_by: str = "main_net") -> dict:
    """查询板块资金流向"""
    trade_date = trade_date or date.today().isoformat()
    allowed_sorts = {"main_net", "total_net", "change_pct", "rise_count"}
    sort_field = sort_by if sort_by in allowed_sorts else "main_net"

    async with engine.begin() as conn:
        result = await conn.execute(text(f"""
            SELECT * FROM sector_flow WHERE trade_date = :d
            ORDER BY {sort_field} DESC NULLS LAST LIMIT :l
        """), {"d": trade_date, "l": limit})
        items = [dict(row._mapping) for row in result]

        total_result = await conn.execute(
            text("SELECT COUNT(*) FROM sector_flow WHERE trade_date = :d"), {"d": trade_date})
        total = total_result.scalar()

    return {"ok": True, "date": trade_date, "total": total, "items": items}


async def query_capital_detail(code: str, days: int = 10) -> dict:
    """查询个股资金流历史"""
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT * FROM capital_flow WHERE code = :c ORDER BY trade_date DESC LIMIT :l
        """), {"c": code, "l": days})
        items = [dict(row._mapping) for row in result]
    return {"ok": True, "code": code, "items": items}


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
