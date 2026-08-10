"""板块热力图 + 板块轮动服务"""
import logging
from datetime import date
from typing import Optional
from sqlalchemy import text
from app.database import engine
from app.liangmai.client import liangmai

log = logging.getLogger("sector.service")


# ───────────────── 板块热力图 ─────────────────

async def fetch_sector_heatmap(trade_date: str = None) -> dict:
    """拉取板块热力图数据（板块涨跌 + 资金流）

    调用量脉 base_bk_flow_history 获取板块资金流向，
    结合已入库的 sector_flow 数据生成热力图。
    """
    trade_date = trade_date or date.today().isoformat()

    # 复用 sector_flow 表（capital_service 已写入）
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT sector_code, sector_name, change_pct, main_net, total_net,
                   rise_count, fall_count, leader_code, leader_name, leader_pct
            FROM sector_flow WHERE trade_date = :d ORDER BY change_pct DESC
        """), {"d": trade_date})
        items = [dict(row._mapping) for row in result]

    if items:
        return {"ok": True, "date": trade_date, "count": len(items), "source": "db", "items": items}

    # DB 无数据，尝试拉取
    result = await liangmai.call("base_bk_flow_history", params={"tradeDate": trade_date}, ttl=0)
    if not result.get("ok"):
        result = await liangmai.call("board_flow_history", params={"date": trade_date}, ttl=0)
    if not result.get("ok"):
        return {"ok": False, "msg": f"拉取失败: {result.get('msg')}"}

    data = result.get("data")
    raw_items = data if isinstance(data, list) else data.get("list", data.get("items", []))
    if not raw_items:
        return {"ok": True, "count": 0, "items": []}

    # 解析
    parsed = []
    for s in raw_items:
        code = s.get("bkCode", s.get("code", s.get("sector_code", "")))
        if not code:
            continue
        parsed.append({
            "sector_code": code,
            "sector_name": s.get("bkName", s.get("name", s.get("sector_name", ""))),
            "change_pct": _float(s.get("changePct", s.get("change_pct", s.get("zf", 0)))),
            "main_net": _int(s.get("mainNet", s.get("main_net", s.get("zljlr", 0)))),
            "total_net": _int(s.get("totalNet", s.get("total_net", 0))),
            "rise_count": _int(s.get("riseCount", s.get("rise_count", s.get("upNum", 0)))),
            "fall_count": _int(s.get("fallCount", s.get("fall_count", s.get("downNum", 0)))),
            "leader_code": s.get("leaderCode", s.get("leader_code", s.get("topCode", ""))),
            "leader_name": s.get("leaderName", s.get("leader_name", s.get("topName", ""))),
            "leader_pct": _float(s.get("leaderPct", s.get("leader_pct", s.get("topPct", 0)))),
        })

    return {"ok": True, "date": trade_date, "count": len(parsed), "source": "api", "items": parsed}


# ───────────────── 板块轮动分析 ─────────────────

async def query_sector_rotation(days: int = 5, top_n: int = 20) -> dict:
    """板块轮动分析：近 N 天板块涨跌变化，识别轮动趋势

    取最近 N 个交易日的 sector_flow 数据，
    计算每个板块的累计涨幅和资金流向变化。
    """
    async with engine.begin() as conn:
        # 获取最近 N 天数据
        result = await conn.execute(text("""
            SELECT trade_date, sector_code, sector_name, change_pct, main_net, total_net,
                   rise_count, fall_count
            FROM sector_flow
            ORDER BY trade_date DESC
            LIMIT :limit
        """), {"limit": days * 500})
        rows = [dict(row._mapping) for row in result]

    if not rows:
        return {"ok": True, "msg": "无板块数据", "rotation": []}

    # 按板块聚合
    from collections import defaultdict
    sector_data = defaultdict(lambda: {"name": "", "days": [], "total_pct": 0, "total_main_net": 0})

    for r in rows:
        code = r["sector_code"]
        sector_data[code]["name"] = r["sector_name"]
        sector_data[code]["days"].append({
            "date": r["trade_date"],
            "pct": r["change_pct"] or 0,
            "main_net": r["main_net"] or 0,
        })
        sector_data[code]["total_pct"] += r["change_pct"] or 0
        sector_data[code]["total_main_net"] += r["main_net"] or 0

    # 排序：按累计涨幅
    ranked = sorted(
        sector_data.items(),
        key=lambda x: x[1]["total_pct"],
        reverse=True,
    )

    rotation = []
    for code, info in ranked[:top_n]:
        # 轮动趋势：对比前半和后半
        day_list = sorted(info["days"], key=lambda x: x["date"])
        mid = len(day_list) // 2
        if mid > 0:
            recent_avg = sum(d["pct"] for d in day_list[:mid]) / mid
            older_avg = sum(d["pct"] for d in day_list[mid:]) / max(len(day_list) - mid, 1)
            trend = "rising" if recent_avg > older_avg * 1.1 else ("falling" if recent_avg < older_avg * 0.9 else "stable")
        else:
            trend = "unknown"

        rotation.append({
            "sector_code": code,
            "sector_name": info["name"],
            "total_pct": round(info["total_pct"], 2),
            "total_main_net": info["total_main_net"],
            "days_count": len(info["days"]),
            "trend": trend,
            "daily": day_list,
        })

    return {"ok": True, "days": days, "rotation": rotation}


# ───────────────── 板块树形结构 ─────────────────

async def fetch_sector_tree() -> dict:
    """拉取板块树形结构（行业 + 概念）"""
    result = await liangmai.call("sector_tree", ttl=3600)
    if not result.get("ok"):
        return {"ok": False, "msg": result.get("msg")}

    data = result.get("data")
    items = data if isinstance(data, list) else data.get("list", data.get("items", []))
    return {"ok": True, "count": len(items) if items else 0, "items": items or []}


async def fetch_sector_stocks(sector_code: str) -> dict:
    """拉取板块成分股"""
    result = await liangmai.call("sector_constituents", params={"bkCode": sector_code}, ttl=300)
    if not result.get("ok"):
        return {"ok": False, "msg": result.get("msg")}

    data = result.get("data")
    items = data if isinstance(data, list) else data.get("list", data.get("items", []))
    return {"ok": True, "sector_code": sector_code, "count": len(items) if items else 0, "items": items or []}


# ───────────────── 板块竞价热度（轮动前兆） ─────────────────

async def fetch_sector_auction(trade_date: str = None) -> dict:
    """拉取板块竞价热度（量脉 base_bkjjzq）"""
    trade_date = trade_date or date.today().isoformat()
    result = await liangmai.call("base_bkjjzq", params={"tradeDate": trade_date}, ttl=0)
    if not result.get("ok"):
        return {"ok": False, "msg": result.get("msg")}

    data = result.get("data")
    items = data if isinstance(data, list) else data.get("list", data.get("items", []))
    return {"ok": True, "date": trade_date, "count": len(items) if items else 0, "items": items or []}


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
