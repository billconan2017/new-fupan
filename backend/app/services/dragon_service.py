"""龙虎榜 + 游资服务"""
import logging
from datetime import date
from typing import Optional
from sqlalchemy import text
from app.database import engine
from app.liangmai.client import liangmai
from app.liangmai.parsing import dragon_records, number, source_date, records
import hashlib

log = logging.getLogger("dragon.service")


async def fetch_dragon_tiger(trade_date: str = None) -> dict:
    """
    拉取龙虎榜数据并写入数据库

    量脉接口: dragonTiger
    写入表: dragon_tiger + dragon_tiger_seats
    """
    from app.utils import is_dragon_tiger_available, parse_trade_date
    trade_date = parse_trade_date(trade_date)

    # 龙虎榜时间校验：交易日15:30前不可查
    available, msg = is_dragon_tiger_available(trade_date)
    if not available:
        return {"ok": False, "msg": msg}

    result = await liangmai.call("lhb_daily", params={"date": trade_date}, ttl=0)
    if not result.get("ok"):
        return {"ok": False, "msg": f"量脉调用失败: {result.get('msg')}"}

    data = result.get("data")
    if not data:
        return {"ok": True, "count": 0, "msg": "无龙虎榜数据"}

    items = dragon_records(data)
    if not items:
        return {"ok": True, "count": 0}

    # 写入主表和席位明细
    main_count = await _insert_dragon_tiger(trade_date, items)
    seat_count = await _insert_dragon_seats(trade_date, items)

    log.info(f"龙虎榜写入完成: {main_count} 只, {seat_count} 个席位")
    return {"ok": True, "stocks": main_count, "seats": seat_count, "date": trade_date}


async def _insert_dragon_tiger(trade_date: str, items: list) -> int:
    """写入龙虎榜主表"""
    rows = []
    for s in items:
        code = s.get("thsCode", s.get("c", s.get("code", s.get("dm", ""))))
        if not code:
            continue
        rows.append({
            "trade_date": trade_date,
            "code": code,
            "name": s.get("n", s.get("name", "")),
            "pct_chg": _float(s.get("chg", s.get("pc", s.get("pct_chg")))),
            "close": _float(s.get("close")),
            "buy_amount": _wan(s.get("buyAmount")),
            "sell_amount": _wan(s.get("sellAmount")),
            "turnover": _float(s.get("hs", s.get("turnover"))),
            "amount": _float(s.get("cje", s.get("amount"))),
            "net_amount": (_wan(s["buyAmount"]) - _wan(s["sellAmount"]))
                if number(s.get("buyAmount")) is not None and number(s.get("sellAmount")) is not None else None,
            "reason": s.get("reason", s.get("lhb_reason", "")),
        })

    if not rows:
        return 0

    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM dragon_tiger WHERE trade_date = :d"), {"d": trade_date})
        await conn.execute(text("""
            INSERT INTO dragon_tiger (trade_date, code, name, close, pct_chg, reason, buy_amount, sell_amount, net_amount)
            VALUES (:trade_date, :code, :name, :close, :pct_chg, :reason, :buy_amount, :sell_amount, :net_amount)
        """), rows)
    return len(rows)


async def _insert_dragon_seats(trade_date: str, items: list) -> int:
    """写入龙虎榜席位明细"""
    rows = []
    for s in items:
        code = s.get("thsCode", s.get("c", s.get("code", s.get("dm", ""))))
        if not code:
            continue
        # 席位数据可能在 seats/buy_seats/sell_seats 字段
        seats = s.get("seats", [])
        if not seats:
            # 尝试 buy_seats + sell_seats
            for seat in (s.get("buy_seats", []) or []):
                rows.append(_parse_seat(trade_date, code, seat, "buy"))
            for seat in (s.get("sell_seats", []) or []):
                rows.append(_parse_seat(trade_date, code, seat, "sell"))
        else:
            for seat in seats:
                direction = seat.get("type", seat.get("direction", "buy"))
                rows.append(_parse_seat(trade_date, code, seat, direction))

    rows = [r for r in rows if r is not None]
    if not rows:
        return 0

    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM dragon_tiger_seats WHERE trade_date = :d"), {"d": trade_date})
        await conn.execute(text("""
            INSERT INTO dragon_tiger_seats (trade_date, code, seat_name, seat_type, amount, rank)
            VALUES (:trade_date, :code, :seat_name, :seat_type, :amount, :rank)
        """), rows)
    return len(rows)


def _parse_seat(trade_date: str, code: str, seat: dict, direction: str) -> Optional[dict]:
    """解析单个席位"""
    name = seat.get("name", seat.get("seat_name", seat.get("trader_name", "")))
    if not name:
        return None
    return {
        "trade_date": trade_date,
        "code": code,
        "seat_name": name,
        "seat_type": direction,
        "amount": _float(seat.get("amount", seat.get("buy_amount", seat.get("sell_amount")))),
        "rank": _int(seat.get("rank", seat.get("seat_rank"))),
    }


# ───────────────── 游资模块 ─────────────────

async def fetch_youzi_all(trade_date: str = None) -> dict:
    """
    拉取游资全景数据

    量脉接口: hotmoney_all (youzi_all)
    写入表: youzi_info + youzi_trades
    """
    trade_date = trade_date or date.today().isoformat()

    result = await liangmai.call("lhb_trader_records", params={"date": trade_date}, ttl=0)
    if not result.get("ok"):
        return {"ok": False, "msg": f"量脉调用失败: {result.get('msg')}"}

    data = result.get("data")
    if not data:
        return {"ok": True, "count": 0, "msg": "无游资数据"}

    items = normalize_youzi(data, trade_date)
    if not items:
        return {"ok": True, "count": 0}

    # 写入游资信息和交易记录
    info_count = await _insert_youzi_info(items)
    trade_count = await _insert_youzi_trades(trade_date, items)

    log.info(f"游资全景写入完成: {info_count} 个游资, {trade_count} 条交易")
    return {"ok": True, "youzis": info_count, "trades": trade_count, "date": trade_date}


async def _insert_youzi_info(items: list) -> int:
    """写入游资基础信息（upsert）"""
    rows = []
    for yz in items:
        yz_id = yz.get("id", yz.get("youzi_id", yz.get("hotmoney_id", "")))
        yz_name = yz.get("name", yz.get("youzi_name", yz.get("hotmoney_name", "")))
        if not yz_id or not yz_name:
            continue
        rows.append({
            "youzi_id": str(yz_id),
            "youzi_name": yz_name,
            "youzi_type": yz.get("type", yz.get("youzi_type", "")),
        })

    if not rows:
        return 0

    async with engine.begin() as conn:
        for r in rows:
            await conn.execute(text("""
                INSERT INTO youzi_info (youzi_id, youzi_name, youzi_type, updated_at)
                VALUES (:youzi_id, :youzi_name, :youzi_type, NOW())
                ON CONFLICT (youzi_id) DO UPDATE SET
                    youzi_name = EXCLUDED.youzi_name,
                    youzi_type = EXCLUDED.youzi_type,
                    updated_at = NOW()
            """), r)
    return len(rows)


async def _insert_youzi_trades(trade_date: str, items: list) -> int:
    """写入游资交易记录"""
    rows = []
    for yz in items:
        yz_id = yz.get("id", yz.get("youzi_id", yz.get("hotmoney_id", "")))
        yz_name = yz.get("name", yz.get("youzi_name", yz.get("hotmoney_name", "")))

        # 解析买入/卖出股票
        for direction_key, direction in [("buy_list", "buy"), ("sell_list", "sell"),
                                          ("buys", "buy"), ("sells", "sell")]:
            stock_list = yz.get(direction_key, [])
            if not stock_list:
                continue
            for stk in stock_list:
                code = stk.get("c", stk.get("code", stk.get("dm", "")))
                if not code:
                    continue
                rows.append({
                    "trade_date": trade_date,
                    "youzi_id": str(yz_id),
                    "youzi_name": yz_name,
                    "code": code,
                    "name": stk.get("n", stk.get("name", "")),
                    "direction": direction,
                    "amount": _float(stk.get("amount", stk.get("cje"))),
                })

    if not rows:
        return 0

    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM youzi_trades WHERE trade_date = :d"), {"d": trade_date})
        await conn.execute(text("""
            INSERT INTO youzi_trades (trade_date, youzi_id, youzi_name, code, name, direction, amount)
            VALUES (:trade_date, :youzi_id, :youzi_name, :code, :name, :direction, :amount)
        """), rows)
    return len(rows)


async def fetch_youzi_stock(code: str, trade_date: str = None) -> dict:
    """拉取个股游资操作记录"""
    trade_date = trade_date or date.today().isoformat()
    result = await liangmai.call("lhb_stock_trader_records", params={"code": code, "startDate": trade_date, "endDate": trade_date}, ttl=60)
    return result


async def fetch_youzi_name(name: str, trade_date: str = None) -> dict:
    """拉取指定游资的历史操作"""
    trade_date = trade_date or date.today().isoformat()
    result = await liangmai.call("lhb_trader_record_history", params={"yzmc": name, "date": trade_date}, ttl=60)
    return result


# ───────────────── 查询接口 ─────────────────

async def query_dragon_tiger(trade_date: str = None, limit: int = 50, offset: int = 0) -> dict:
    """查询龙虎榜"""
    trade_date = trade_date or date.today().isoformat()
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT * FROM dragon_tiger WHERE trade_date = :d ORDER BY net_amount DESC LIMIT :l OFFSET :o
        """), {"d": trade_date, "l": limit, "o": offset})
        items = [dict(row._mapping) for row in result]

        # 附带席位数据
        for item in items:
            seats_result = await conn.execute(text("""
                SELECT * FROM dragon_tiger_seats WHERE trade_date = :d AND code = :c ORDER BY rank
            """), {"d": trade_date, "c": item["code"]})
            item["seats"] = [dict(r._mapping) for r in seats_result]

        count_result = await conn.execute(
            text("SELECT COUNT(*) FROM dragon_tiger WHERE trade_date = :d"), {"d": trade_date})
        total = count_result.scalar()

    return {"ok": True, "date": trade_date, "total": total, "items": items}


async def query_youzi_list(trade_date: str = None) -> dict:
    """查询游资列表"""
    trade_date = trade_date or date.today().isoformat()
    async with engine.begin() as conn:
        # 查当日有操作的游资
        result = await conn.execute(text("""
            SELECT DISTINCT y.youzi_id, y.youzi_name, y.youzi_type,
                   COUNT(*) as trade_count,
                   SUM(CASE WHEN t.direction = 'buy' THEN t.amount ELSE 0 END) as buy_amount,
                   SUM(CASE WHEN t.direction = 'sell' THEN t.amount ELSE 0 END) as sell_amount
            FROM youzi_trades t
            JOIN youzi_info y ON t.youzi_id = y.youzi_id
            WHERE t.trade_date = :d
            GROUP BY y.youzi_id, y.youzi_name, y.youzi_type
            ORDER BY buy_amount DESC
        """), {"d": trade_date})
        items = [dict(row._mapping) for row in result]

    return {"ok": True, "date": trade_date, "total": len(items), "items": items}


async def query_youzi_detail(youzi_id: str, trade_date: str = None, days: int = 30) -> dict:
    """查询单个游资详情及近期操作"""
    trade_date = trade_date or date.today().isoformat()
    async with engine.begin() as conn:
        # 游资信息
        info_result = await conn.execute(text(
            "SELECT * FROM youzi_info WHERE youzi_id = :id"), {"id": youzi_id})
        info = info_result.first()
        if not info:
            return {"ok": False, "msg": f"游资 {youzi_id} 不存在"}

        # 近期交易
        trades_result = await conn.execute(text("""
            SELECT * FROM youzi_trades WHERE youzi_id = :id
            ORDER BY trade_date DESC LIMIT :l
        """), {"id": youzi_id, "l": days * 5})
        trades = [dict(row._mapping) for r in trades_result]

    return {"ok": True, "info": dict(info._mapping), "trades": trades}


async def fetch_all_dragon(trade_date: str = None) -> dict:
    """一次性拉取龙虎榜+游资全部数据"""
    trade_date = trade_date or date.today().isoformat()
    dragon = await fetch_dragon_tiger(trade_date)
    youzi = await fetch_youzi_all(trade_date)
    return {"dragon_tiger": dragon, "youzi": youzi}


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


def _wan(value):
    n = number(value)
    return n * 10000 if n is not None else None


def normalize_youzi(data, trade_date):
    grouped = {}
    for row in records(data):
        name = row.get("yzmc")
        code = row.get("gpdm")
        if not name or not code or (row.get("rq") and source_date(row["rq"]) != trade_date):
            continue
        entry = grouped.setdefault(name, {"id": hashlib.sha256(name.encode()).hexdigest()[:24],
                                           "name": name, "buy_list": [], "sell_list": []})
        for key, bucket in (("mrje", "buy_list"), ("mcje", "sell_list")):
            amount = number(row.get(key))
            if amount is not None and amount > 0:
                entry[bucket].append({"code": code, "name": row.get("gpmc"), "amount": amount})
    return list(grouped.values())
