"""竞价数据服务 — 板块竞价/个股竞价/封单排行/一字涨停"""
import logging
from datetime import date
from typing import Optional
from sqlalchemy import text
from app.database import engine
from app.liangmai.client import liangmai
from app.liangmai.parsing import records

log = logging.getLogger("auction.service")


async def fetch_auction_sectors(trade_date: str = None) -> dict:
    """拉取板块竞价数据 → auction_sector"""
    trade_date = trade_date or date.today().isoformat()
    result = await liangmai.call("auction_morning_sector", params={"startDate": trade_date, "endDate": trade_date, "type": "1"}, ttl=0)
    if not result.get("ok"):
        return {"ok": False, "msg": result.get("msg")}

    data = result.get("data")
    items = records(data)
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
            "pct_chg": _float(s.get("changePct", s.get("change_pct", s.get("zf")))),
            "amount": _float(s.get("amount", s.get("cje"))),
            "rise_count": _int(s.get("riseCount", s.get("rise_count", s.get("upNum")))),
            "fall_count": _int(s.get("fallCount", s.get("fall_count", s.get("downNum")))),
        })

    if not rows:
        return {"ok": True, "count": 0}

    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM auction_sector WHERE trade_date = :d"), {"d": trade_date})
        await conn.execute(text("""
            INSERT INTO auction_sector (trade_date, sector_code, sector_name, pct_chg, amount, rise_count, fall_count)
            VALUES (:trade_date, :sector_code, :sector_name, :pct_chg, :amount, :rise_count, :fall_count)
        """), rows)

    log.info(f"板块竞价写入: {len(rows)} 条")
    return {"ok": True, "count": len(rows), "date": trade_date}


async def fetch_auction_stocks(trade_date: str = None) -> dict:
    """拉取个股竞价数据 → auction_stock"""
    trade_date = trade_date or date.today().isoformat()
    result = await liangmai.call("auction_morning_grab_amount", params={"tradeDate": trade_date, "period": "0", "type": "1"}, ttl=0)
    if not result.get("ok"):
        return {"ok": False, "msg": result.get("msg")}

    data = result.get("data")
    items = records(data)
    if not items:
        return {"ok": True, "count": 0}

    rows = []
    for s in items:
        code = s.get("code", s.get("c", s.get("dm", "")))
        if not code:
            continue
        rows.append({
            "trade_date": trade_date,
            "code": code,
            "name": s.get("name", s.get("n", "")),
            "open_price": _float(s.get("openPrice", s.get("open", s.get("open_price")))),
            "pre_close": _float(s.get("preClose", s.get("pre_close", s.get("yc")))),
            "pct_chg": _float(s.get("changePct", s.get("change_pct", s.get("zf", s.get("pc"))))),
            "amount": _float(s.get("amount", s.get("cje", s.get("openAmt")))),
            "volume": _int(s.get("volume", s.get("v", s.get("auction_volume")))),
        })

    if not rows:
        return {"ok": True, "count": 0}

    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM auction_stock WHERE trade_date = :d"), {"d": trade_date})
        await conn.execute(text("""
            INSERT INTO auction_stock (trade_date, code, name, open_price, pre_close, pct_chg, amount, volume)
            VALUES (:trade_date, :code, :name, :open_price, :pre_close, :pct_chg, :amount, :volume)
        """), rows)

    log.info(f"个股竞价写入: {len(rows)} 条")
    return {"ok": True, "count": len(rows), "date": trade_date}


async def fetch_auction_tail(trade_date: str = None) -> dict:
    """拉取竞价封单排行 → auction_tail（合并 wt/cje/close/zf 四种类型）"""
    trade_date = trade_date or date.today().isoformat()

    tail_apis = {
        "wt": "auction_tail_grab_amount",
        "cje": "auction_tail_grab_turnover",
        "close": "auction_tail_grab_close",
        "zf": "auction_tail_grab_change",
    }

    all_rows = []
    failed_types = []
    for tail_type, api in tail_apis.items():
        result = await liangmai.call(api, params={"tradeDate": trade_date, "period": "1", "type": {"wt": "1", "cje": "2", "close": "3", "zf": "4"}[tail_type]}, ttl=0)
        if not result.get("ok"):
            failed_types.append(tail_type)
            log.warning(f"封单 {tail_type} 拉取失败: {result.get('msg')}")
            continue

        data = result.get("data")
        items = records(data)
        if not items:
            continue

        for rank, s in enumerate(items, 1):
            code = s.get("code", s.get("c", s.get("dm", "")))
            if not code:
                continue
            all_rows.append({
                "trade_date": trade_date,
                "code": code,
                "name": s.get("name", s.get("n", "")),
                "tail_type": tail_type,
                "value": _float(s.get({"wt": "qcwtje", "cje": "qccje", "close": "closeAmt", "zf": "qczf"}[tail_type])),
                "rank": _int(s.get("rank", rank)),
            })

    if not all_rows:
        return {"ok": not failed_types, "count": 0, "dataMissing": True, "failedTypes": failed_types}

    async with engine.begin() as conn:
        for tail_type in {r["tail_type"] for r in all_rows}:
            await conn.execute(text("DELETE FROM auction_tail WHERE trade_date = :d AND tail_type=:t"), {"d": trade_date, "t": tail_type})
        await conn.execute(text("""
            INSERT INTO auction_tail (trade_date, code, name, tail_type, value, rank)
            VALUES (:trade_date, :code, :name, :tail_type, :value, :rank)
        """), all_rows)

    log.info(f"竞价封单写入: {len(all_rows)} 条")
    return {"ok": not failed_types, "count": len(all_rows), "date": trade_date, "failedTypes": failed_types}


async def fetch_auction_yizi(trade_date: str = None) -> dict:
    """拉取一字涨停列表 → auction_yizi"""
    trade_date = trade_date or date.today().isoformat()
    result = await liangmai.call("auction_one_word_limit", params={"tradeDate": trade_date}, ttl=0)
    if not result.get("ok"):
        return {"ok": False, "msg": result.get("msg")}

    data = result.get("data")
    items = records(data)
    if not items:
        return {"ok": True, "count": 0}

    rows = []
    for s in items:
        code = s.get("code", s.get("c", s.get("dm", "")))
        if not code:
            continue
        rows.append({
            "trade_date": trade_date,
            "code": code,
            "name": s.get("name", s.get("n", "")),
            "pct_chg": _float(s.get("changePct", s.get("change_pct", s.get("zf", s.get("pc"))))),
            "amount": _float(s.get("amount", s.get("cje"))),
        })

    if not rows:
        return {"ok": True, "count": 0}

    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM auction_yizi WHERE trade_date = :d"), {"d": trade_date})
        await conn.execute(text("""
            INSERT INTO auction_yizi (trade_date, code, name, pct_chg, amount)
            VALUES (:trade_date, :code, :name, :pct_chg, :amount)
        """), rows)

    log.info(f"一字涨停写入: {len(rows)} 条")
    return {"ok": True, "count": len(rows), "date": trade_date}


async def fetch_all_auction(trade_date: str = None) -> dict:
    """一次性拉取全部竞价数据"""
    trade_date = trade_date or date.today().isoformat()
    return {
        "sectors": await fetch_auction_sectors(trade_date),
        "stocks": await fetch_auction_stocks(trade_date),
        "tail": await fetch_auction_tail(trade_date),
        "yizi": await fetch_auction_yizi(trade_date),
    }


# ───────────────── 查询接口 ─────────────────

async def query_auction_sectors(trade_date: str = None, limit: int = 50) -> dict:
    """查询板块竞价"""
    trade_date = trade_date or date.today().isoformat()
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT * FROM auction_sector WHERE trade_date = :d ORDER BY pct_chg DESC LIMIT :l
        """), {"d": trade_date, "l": limit})
        items = [dict(row._mapping) for row in result]
        total_result = await conn.execute(
            text("SELECT COUNT(*) FROM auction_sector WHERE trade_date = :d"), {"d": trade_date})
        total = total_result.scalar()
    return {"ok": True, "date": trade_date, "total": total, "items": items}


async def query_auction_stocks(trade_date: str = None, limit: int = 50, offset: int = 0,
                                min_pct: float = None, sort_by: str = "pct_chg") -> dict:
    """查询个股竞价"""
    trade_date = trade_date or date.today().isoformat()
    allowed_sorts = {"pct_chg", "amount", "volume"}
    sort_field = sort_by if sort_by in allowed_sorts else "pct_chg"

    where = "WHERE trade_date = :d"
    params = {"d": trade_date, "l": limit, "o": offset}
    if min_pct is not None:
        where += " AND pct_chg >= :min_pct"
        params["min_pct"] = min_pct

    async with engine.begin() as conn:
        result = await conn.execute(text(f"""
            SELECT * FROM auction_stock {where} ORDER BY {sort_field} DESC NULLS LAST LIMIT :l OFFSET :o
        """), params)
        items = [dict(row._mapping) for row in result]
        count_params = {"d": trade_date}
        if min_pct is not None:
            count_params["min_pct"] = min_pct
        total_result = await conn.execute(
            text(f"SELECT COUNT(*) FROM auction_stock {where}".replace("LIMIT :l OFFSET :o", "")),
            count_params)
        total = total_result.scalar()
    return {"ok": True, "date": trade_date, "total": total, "items": items}


async def query_auction_tail(trade_date: str = None, tail_type: str = "wt", limit: int = 30) -> dict:
    """查询封单排行"""
    trade_date = trade_date or date.today().isoformat()
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT * FROM auction_tail WHERE trade_date = :d AND tail_type = :t ORDER BY rank LIMIT :l
        """), {"d": trade_date, "t": tail_type, "l": limit})
        items = [dict(row._mapping) for row in result]
    return {"ok": True, "date": trade_date, "tail_type": tail_type, "items": items}


async def query_auction_yizi(trade_date: str = None) -> dict:
    """查询一字涨停"""
    trade_date = trade_date or date.today().isoformat()
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT * FROM auction_yizi WHERE trade_date = :d ORDER BY amount DESC
        """), {"d": trade_date})
        items = [dict(row._mapping) for row in result]
    return {"ok": True, "date": trade_date, "items": items}


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
