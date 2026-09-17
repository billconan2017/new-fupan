"""资金流向服务 — 个股资金流 + 板块资金流"""
import logging
from datetime import date
from typing import Optional
from sqlalchemy import text
from app.database import engine
from app.liangmai.client import liangmai
from app.liangmai.parsing import records, source_date, number

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
        result = await liangmai.call("flow_stock_history", params={"ts_code": code, "st": trade_date.replace("-", ""), "et": trade_date.replace("-", "")}, ttl=300)
        if not result.get("ok"):
            failed += 1
            continue
        data = result.get("data")
        if not data:
            continue
        # data 可能是 list 或 dict
        items = records(data)
        for item in items:
            if source_date(item.get("t")) != trade_date:
                continue
            large = number(item.get("jlrddcje"))
            super_large = number(item.get("jlrcdcje"))
            rows.append({
                "trade_date": trade_date,
                "code": code,
                "name": item.get("name", item.get("n", "")),
                "main_net": int(large + super_large) if large is not None and super_large is not None else None,
                "super_large_net": _int(super_large), "large_net": _int(large),
                "medium_net": _int(item.get("jlrzdcje")), "small_net": _int(item.get("jlrxdcje")),
                "main_pct": None,
            })

    if not rows:
        return {"ok": False, "dataMissing": True, "count": 0, "failed": failed, "msg": "请求日期暂无资金流数据"}

    # 写入数据库
    async with engine.begin() as conn:
        await conn.execute(text("""
            INSERT INTO capital_flow (trade_date, code, name, main_net, super_large_net, large_net, medium_net, small_net, main_pct)
            VALUES (:trade_date, :code, :name, :main_net, :super_large_net, :large_net, :medium_net, :small_net, :main_pct)
            ON CONFLICT (trade_date, code) DO UPDATE SET
                main_net=EXCLUDED.main_net, super_large_net=EXCLUDED.super_large_net,
                large_net=EXCLUDED.large_net, medium_net=EXCLUDED.medium_net, small_net=EXCLUDED.small_net
        """), rows)

    log.info(f"个股资金流写入: {len(rows)} 条, 失败 {failed}")
    return {"ok": failed == 0 and len(rows) == len(target_codes), "count": len(rows), "failed": failed, "date": trade_date, "dataMissing": len(rows) != len(target_codes)}


# ───────────────── 板块资金流向 ─────────────────

async def fetch_sector_flow(trade_date: str = None) -> dict:
    """Use official BK codes; history takes one bkCode, never invented bkCodes."""
    trade_date = trade_date or date.today().isoformat()
    catalog = await liangmai.call("sector_plate_code", ttl=3600)
    if not catalog.get("ok"):
        return catalog
    sectors = records(catalog.get("data"))
    if not sectors:
        return {"ok": False, "dataMissing": True, "msg": "量脉板块代码目录暂无数据", "count": 0}
    rows, missing = [], []
    for sector in sectors:
        code = sector.get("plateCode")
        if not code:
            continue
        response = await liangmai.call("flow_sector_history", {"bkCode": code}, ttl=300)
        item = next((r for r in records(response.get("data")) if source_date(r.get("time")) == trade_date), None)
        if not response.get("ok") or item is None:
            missing.append(code)
            continue
        rows.append({"trade_date": trade_date, "sector_code": code, "sector_name": sector.get("name"),
                     "main_net": _int(item.get("mainAmount")), "retail_net": _int(item.get("minAmount")),
                     "total_net": None, "change_pct": None, "rise_count": None, "fall_count": None,
                     "leader_code": None, "leader_name": None, "leader_pct": None})
    if rows:
        async with engine.begin() as conn:
            # Replace only successfully fetched sectors, preserving failed sectors' existing history.
            for row in rows:
                await conn.execute(text("DELETE FROM sector_flow WHERE trade_date=:trade_date AND sector_code=:sector_code"), row)
            await conn.execute(text("""
                INSERT INTO sector_flow (trade_date, sector_code, sector_name, main_net, retail_net, total_net,
                    change_pct, rise_count, fall_count, leader_code, leader_name, leader_pct)
                VALUES (:trade_date, :sector_code, :sector_name, :main_net, :retail_net, :total_net,
                    :change_pct, :rise_count, :fall_count, :leader_code, :leader_name, :leader_pct)
            """), rows)
    return {"ok": bool(rows) and not missing, "date": trade_date, "count": len(rows),
            "dataMissing": bool(missing) or not rows, "missingCodes": missing}


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
