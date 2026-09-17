"""自动盘后复盘报告服务

聚合全部 6 个模块数据，生成结构化盘后复盘报告。
模块数据来源：
  1. 情绪周期 → emotion_cycle
  2. 涨停池 / 强势股池 → limit_up_pool / strong_pool
  3. 跌停池 → limit_down_pool
  4. 炸板池 → broken_board_pool
  5. 龙虎榜 → dragon_tiger
  6. 资金流向 → capital_flow
  7. 风险预警 → risk_alarms
"""
import json
import logging
from datetime import date
from typing import Optional
from sqlalchemy import text
from app.database import engine

log = logging.getLogger("review.service")


# ═══════════════════════ 生成报告 ═══════════════════════

async def generate_review(trade_date: str = None) -> dict:
    """生成盘后复盘报告（聚合全部模块 → 写入 review_reports）"""
    trade_date = trade_date or date.today().isoformat()

    # 1. 并行收集各模块数据
    emotion = await _query_emotion(trade_date)
    limit_up = await _query_limit_up(trade_date)
    limit_down = await _query_limit_down(trade_date)
    broken_board = await _query_broken_board(trade_date)
    dragon = await _query_dragon_tiger(trade_date)
    capital = await _query_capital_flow(trade_date)
    strong = await _query_strong_stocks(trade_date)
    risks = await _query_risk_alarms(trade_date)
    overview = await _query_market_overview(trade_date)

    # 2. 综合评分
    overall_score, overall_comment = _calculate_score(
        emotion, limit_up, limit_down, broken_board, dragon, capital, overview
    )

    # 3. 组装报告
    report = {
        "trade_date": trade_date,
        "market_overview": overview,
        "emotion_summary": emotion,
        "limit_up_analysis": limit_up,
        "limit_down_analysis": limit_down,
        "broken_board_analysis": broken_board,
        "dragon_tiger_summary": dragon,
        "capital_summary": capital,
        "strong_stocks": strong,
        "risk_alarms": risks,
        "overall_score": overall_score,
        "overall_comment": overall_comment,
    }

    # 4. 写入数据库
    await _save_report(trade_date, report)

    log.info(f"复盘报告生成: date={trade_date} score={overall_score}")
    return {"ok": True, "date": trade_date, "report": report}


async def generate_review_snapshot(trade_date: str = None) -> dict:
    """生成报告但不写库（预览模式）"""
    trade_date = trade_date or date.today().isoformat()

    emotion = await _query_emotion(trade_date)
    limit_up = await _query_limit_up(trade_date)
    limit_down = await _query_limit_down(trade_date)
    broken_board = await _query_broken_board(trade_date)
    dragon = await _query_dragon_tiger(trade_date)
    capital = await _query_capital_flow(trade_date)
    strong = await _query_strong_stocks(trade_date)
    risks = await _query_risk_alarms(trade_date)
    overview = await _query_market_overview(trade_date)

    overall_score, overall_comment = _calculate_score(
        emotion, limit_up, limit_down, broken_board, dragon, capital, overview
    )

    return {
        "ok": True,
        "date": trade_date,
        "report": {
            "trade_date": trade_date,
            "market_overview": overview,
            "emotion_summary": emotion,
            "limit_up_analysis": limit_up,
            "limit_down_analysis": limit_down,
            "broken_board_analysis": broken_board,
            "dragon_tiger_summary": dragon,
            "capital_summary": capital,
            "strong_stocks": strong,
            "risk_alarms": risks,
            "overall_score": overall_score,
            "overall_comment": overall_comment,
        },
    }


# ═══════════════════════ 查询报告 ═══════════════════════

async def query_review(trade_date: str = None) -> dict:
    """查询指定日期的复盘报告"""
    trade_date = trade_date or date.today().isoformat()
    async with engine.begin() as conn:
        result = await conn.execute(text(
            "SELECT * FROM review_reports WHERE trade_date = :d"
        ), {"d": trade_date})
        row = result.first()

    if not row:
        return {"ok": False, "msg": f"{trade_date} 暂无复盘报告，请先生成"}

    report = _row_to_report(row)
    return {"ok": True, "date": trade_date, "report": report}


async def query_review_list(limit: int = 30, offset: int = 0) -> dict:
    """查询复盘报告列表（分页）"""
    async with engine.begin() as conn:
        count_r = await conn.execute(text("SELECT COUNT(*) FROM review_reports"))
        total = count_r.scalar()

        result = await conn.execute(text("""
            SELECT trade_date, overall_score, overall_comment, created_at
            FROM review_reports ORDER BY trade_date DESC LIMIT :l OFFSET :o
        """), {"l": limit, "o": offset})
        rows = [dict(r._mapping) for r in result]

    return {"ok": True, "total": total, "items": rows}


# ═══════════════════════ 数据采集层 ═══════════════════════

async def _query_emotion(trade_date: str) -> dict:
    """采集情绪周期"""
    async with engine.begin() as conn:
        r = await conn.execute(text(
            "SELECT * FROM emotion_cycle WHERE trade_date = :d"
        ), {"d": trade_date})
        row = r.first()
    if not row:
        return {"available": False, "msg": "情绪数据未入库"}
    d = dict(row._mapping)
    return {
        "available": True,
        "emotion_score": d.get("emotion_score"),
        "cycle_phase": d.get("cycle_phase"),
        "limit_up_count": d.get("limit_up_count"),
        "limit_down_count": d.get("limit_down_count"),
        "height_board": d.get("height_board"),
        "continue_count": d.get("continue_count"),
        "broken_count": d.get("broken_count"),
        "avg_change_pct": d.get("avg_change_pct"),
    }


async def _query_limit_up(trade_date: str) -> dict:
    """采集涨停池"""
    async with engine.begin() as conn:
        r = await conn.execute(text(
            "SELECT * FROM limit_up_pool WHERE trade_date = :d ORDER BY pct_chg DESC"
        ), {"d": trade_date})
        rows = [dict(row._mapping) for row in r]
    count = len(rows)
    if count == 0:
        return {"available": False, "count": 0}

    # 连板统计
    consecutive_map = {}
    for r in rows:
        c = r.get("consecutive") or 1
        consecutive_map[c] = consecutive_map.get(c, 0) + 1

    # 行业分布
    industry_map = {}
    for r in rows:
        ind = r.get("industry") or "未知"
        industry_map[ind] = industry_map.get(ind, 0) + 1

    top_industries = sorted(industry_map.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "available": True,
        "count": count,
        "consecutive_distribution": {str(k): v for k, v in sorted(consecutive_map.items(), reverse=True)},
        "top_industries": [{"industry": k, "count": v} for k, v in top_industries],
        "highest_consecutive": max(consecutive_map.keys()) if consecutive_map else 0,
        "samples": rows[:10],
    }


async def _query_limit_down(trade_date: str) -> dict:
    """采集跌停池"""
    async with engine.begin() as conn:
        r = await conn.execute(text(
            "SELECT * FROM limit_down_pool WHERE trade_date = :d ORDER BY pct_chg ASC"
        ), {"d": trade_date})
        rows = [dict(row._mapping) for row in r]
    count = len(rows)
    if count == 0:
        return {"available": False, "count": 0}

    industry_map = {}
    for r in rows:
        ind = r.get("industry") or "未知"
        industry_map[ind] = industry_map.get(ind, 0) + 1
    top_industries = sorted(industry_map.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "available": True,
        "count": count,
        "top_industries": [{"industry": k, "count": v} for k, v in top_industries],
        "samples": rows[:10],
    }


async def _query_broken_board(trade_date: str) -> dict:
    """采集炸板池"""
    async with engine.begin() as conn:
        r = await conn.execute(text(
            "SELECT * FROM broken_board_pool WHERE trade_date = :d"
        ), {"d": trade_date})
        rows = [dict(row._mapping) for row in r]
    count = len(rows)
    if count == 0:
        return {"available": False, "count": 0}

    return {
        "available": True,
        "count": count,
        "samples": rows[:10],
    }


async def _query_dragon_tiger(trade_date: str) -> dict:
    """采集龙虎榜"""
    async with engine.begin() as conn:
        r = await conn.execute(text(
            "SELECT * FROM dragon_tiger WHERE trade_date = :d ORDER BY net_amount DESC"
        ), {"d": trade_date})
        rows = [dict(row._mapping) for row in r]
    count = len(rows)
    if count == 0:
        return {"available": False, "count": 0}

    net_buy_total = sum(r.get("net_amount") or 0 for r in rows)
    net_buy_positive = sum(1 for r in rows if (r.get("net_amount") or 0) > 0)

    return {
        "available": True,
        "count": count,
        "net_buy_total": net_buy_total,
        "net_buy_positive_count": net_buy_positive,
        "samples": rows[:10],
    }


async def _query_capital_flow(trade_date: str) -> dict:
    """采集资金流向（板块 + 个股 top10）"""
    async with engine.begin() as conn:
        # 个股主力净流入 top10
        r = await conn.execute(text("""
            SELECT code, name, main_net, super_large_net, large_net, main_pct
            FROM capital_flow WHERE trade_date = :d ORDER BY main_net DESC LIMIT 10
        """), {"d": trade_date})
        top_inflow = [dict(row._mapping) for row in r]

        # 个股主力净流出 top10
        r = await conn.execute(text("""
            SELECT code, name, main_net, super_large_net, large_net, main_pct
            FROM capital_flow WHERE trade_date = :d ORDER BY main_net ASC LIMIT 10
        """), {"d": trade_date})
        top_outflow = [dict(row._mapping) for row in r]

        # 整体统计
        r = await conn.execute(text("""
            SELECT
                COUNT(*) as total,
                SUM(main_net) as total_main_net,
                SUM(super_large_net) as total_super_large,
                SUM(large_net) as total_large,
                COUNT(CASE WHEN main_net > 0 THEN 1 END) as inflow_count,
                COUNT(CASE WHEN main_net < 0 THEN 1 END) as outflow_count
            FROM capital_flow WHERE trade_date = :d
        """), {"d": trade_date})
        stats = r.first()

    if not stats or not stats[0]:
        return {"available": False, "msg": "资金流数据未入库"}

    s = dict(stats._mapping)
    return {
        "available": True,
        "total_stocks": s.get("total", 0),
        "total_main_net": s.get("total_main_net", 0),
        "total_super_large_net": s.get("total_super_large", 0),
        "total_large_net": s.get("total_large", 0),
        "inflow_count": s.get("inflow_count", 0),
        "outflow_count": s.get("outflow_count", 0),
        "top_inflow": top_inflow,
        "top_outflow": top_outflow,
    }


async def _query_strong_stocks(trade_date: str) -> dict:
    """采集强势股池"""
    async with engine.begin() as conn:
        r = await conn.execute(text("""
            SELECT code, name, pct_chg, amount, turnover, volume_ratio, industry
            FROM strong_pool WHERE trade_date = :d ORDER BY pct_chg DESC LIMIT 20
        """), {"d": trade_date})
        rows = [dict(row._mapping) for row in r]
    count = len(rows)
    if count == 0:
        return {"available": False, "count": 0}

    industry_map = {}
    for r in rows:
        ind = r.get("industry") or "未知"
        industry_map[ind] = industry_map.get(ind, 0) + 1

    return {
        "available": True,
        "count": count,
        "industry_distribution": industry_map,
        "samples": rows,
    }


async def _query_risk_alarms(trade_date: str) -> dict:
    """采集风险预警"""
    async with engine.begin() as conn:
        r = await conn.execute(text(
            "SELECT * FROM risk_alarms WHERE trade_date = :d ORDER BY created_at DESC"
        ), {"d": trade_date})
        rows = [dict(row._mapping) for row in r]
    return {"available": bool(rows), "count": len(rows), "items": rows}


async def _query_market_overview(trade_date: str) -> dict:
    """采集市场概览（从最新快照统计）"""
    async with engine.begin() as conn:
        # 取当日最后一条快照统计
        r = await conn.execute(text("""
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN pct_chg > 0 THEN 1 END) as rise_count,
                COUNT(CASE WHEN pct_chg < 0 THEN 1 END) as fall_count,
                COUNT(CASE WHEN pct_chg = 0 THEN 1 END) as flat_count,
                SUM(amount) as total_amount,
                AVG(pct_chg) as avg_pct,
                MAX(pct_chg) as max_pct,
                MIN(pct_chg) as min_pct,
                COUNT(CASE WHEN pct_chg >= 9.9 THEN 1 END) as zt_approx,
                COUNT(CASE WHEN pct_chg <= -9.9 THEN 1 END) as dt_approx
            FROM market_snapshot
            WHERE trade_date = :d
            AND snapshot_at = (
                SELECT MAX(snapshot_at) FROM market_snapshot WHERE trade_date = :d
            )
        """), {"d": trade_date})
        row = r.first()

    if not row or not row[0]:
        return {"available": False, "msg": "快照数据未入库"}

    d = dict(row._mapping)
    total = d.get("total", 0) or 0
    rise = d.get("rise_count", 0) or 0
    fall = d.get("fall_count", 0) or 0

    return {
        "available": True,
        "total_stocks": total,
        "rise_count": rise,
        "fall_count": fall,
        "flat_count": d.get("flat_count", 0),
        "rise_ratio": round(rise / total * 100, 1) if total else 0,
        "total_amount_yi": round((d.get("total_amount") or 0) / 1e8, 2),
        "avg_pct_chg": round(d.get("avg_pct") or 0, 2),
        "max_pct_chg": round(d.get("max_pct") or 0, 2),
        "min_pct_chg": round(d.get("min_pct") or 0, 2),
    }


# ═══════════════════════ 综合评分 ═══════════════════════

def _calculate_score(emotion, limit_up, limit_down, broken_board, dragon, capital, overview) -> tuple:
    """综合评分算法 (0-100)"""
    score = 50  # 基准分
    factors = []

    # 涨跌比 (+/- 15分)
    if overview.get("available"):
        ratio = overview.get("rise_ratio", 50)
        delta = (ratio - 50) * 0.3
        score += delta
        factors.append(f"涨跌比{ratio}%({'偏多' if delta > 0 else '偏空'})")

    # 情绪分 (+/- 10分)
    if emotion.get("available"):
        es = emotion.get("emotion_score") or 50
        delta = (es - 50) * 0.2
        score += delta
        factors.append(f"情绪{es}分({emotion.get('cycle_phase', '')})")

    # 涨停数量 (+/- 8分)
    if limit_up.get("available"):
        lu = limit_up.get("count", 0)
        if lu >= 80:
            score += 8
        elif lu >= 50:
            score += 5
        elif lu >= 30:
            score += 2
        elif lu < 15:
            score -= 5
        factors.append(f"涨停{lu}只")

    # 跌停数量 (-分)
    if limit_down.get("available"):
        ld = limit_down.get("count", 0)
        if ld >= 30:
            score -= 10
        elif ld >= 15:
            score -= 5
        elif ld >= 5:
            score -= 2
        factors.append(f"跌停{ld}只")

    # 炸板 (-分)
    if broken_board.get("available"):
        bb = broken_board.get("count", 0)
        if bb >= 20:
            score -= 5
        elif bb >= 10:
            score -= 2
        factors.append(f"炸板{bb}只")

    # 龙虎榜 (+/- 5分)
    if dragon.get("available"):
        net = dragon.get("net_buy_total", 0)
        if net > 0:
            score += 3
        else:
            score -= 3
        factors.append(f"龙虎榜净{'买' if net > 0 else '卖'}")

    # 资金流向 (+/- 5分)
    if capital.get("available"):
        main_net = capital.get("total_main_net", 0)
        if main_net > 0:
            score += 3
        else:
            score -= 3
        factors.append(f"主力净{'流入' if main_net > 0 else '流出'}")

    # 限制范围
    score = max(0, min(100, score))

    # 生成评语
    if score >= 80:
        comment = "强势，情绪高涨，市场赚钱效应好"
    elif score >= 65:
        comment = "偏强，多数个股上涨，题材活跃"
    elif score >= 50:
        comment = "中性，多空均衡，结构性行情"
    elif score >= 35:
        comment = "偏弱，赚钱效应差，注意风险"
    else:
        comment = "弱势，情绪低迷，建议观望"

    return round(score, 1), f"{comment} | {'，'.join(factors[:4])}"


# ═══════════════════════ 持久化 ═══════════════════════

async def _save_report(trade_date: str, report: dict):
    """写入/更新报告"""
    from fastapi.encoders import jsonable_encoder
    report = jsonable_encoder(report)
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM review_reports WHERE trade_date = :d"), {"d": trade_date})
        await conn.execute(text("""
            INSERT INTO review_reports
                (trade_date, market_overview, emotion_summary, limit_up_analysis,
                 limit_down_analysis, broken_board_analysis, dragon_tiger_summary,
                 capital_summary, strong_stocks, risk_alarms, overall_score, overall_comment, raw_data)
            VALUES
                (:trade_date, :market_overview, :emotion_summary, :limit_up_analysis,
                 :limit_down_analysis, :broken_board_analysis, :dragon_tiger_summary,
                 :capital_summary, :strong_stocks, :risk_alarms, :overall_score, :overall_comment, :raw_data)
        """), {
            "trade_date": trade_date,
            "market_overview": json.dumps(report["market_overview"], ensure_ascii=False),
            "emotion_summary": json.dumps(report["emotion_summary"], ensure_ascii=False),
            "limit_up_analysis": json.dumps(report["limit_up_analysis"], ensure_ascii=False),
            "limit_down_analysis": json.dumps(report["limit_down_analysis"], ensure_ascii=False),
            "broken_board_analysis": json.dumps(report["broken_board_analysis"], ensure_ascii=False),
            "dragon_tiger_summary": json.dumps(report["dragon_tiger_summary"], ensure_ascii=False),
            "capital_summary": json.dumps(report["capital_summary"], ensure_ascii=False),
            "strong_stocks": json.dumps(report["strong_stocks"], ensure_ascii=False),
            "risk_alarms": json.dumps(report["risk_alarms"], ensure_ascii=False),
            "overall_score": report["overall_score"],
            "overall_comment": report["overall_comment"],
            "raw_data": json.dumps(report, ensure_ascii=False),
        })


def _row_to_report(row) -> dict:
    """数据库行 → 报告 dict"""
    d = dict(row._mapping)
    fields = [
        "market_overview", "emotion_summary", "limit_up_analysis",
        "limit_down_analysis", "broken_board_analysis", "dragon_tiger_summary",
        "capital_summary", "strong_stocks", "risk_alarms",
    ]
    report = {"trade_date": d["trade_date"]}
    for f in fields:
        raw = d.get(f)
        try:
            report[f] = json.loads(raw) if raw else None
        except (json.JSONDecodeError, TypeError):
            report[f] = raw
    report["overall_score"] = d.get("overall_score")
    report["overall_comment"] = d.get("overall_comment")
    report["created_at"] = str(d.get("created_at", ""))
    return report
