"""情绪周期服务"""
import logging
from datetime import date
from typing import Optional
from sqlalchemy import text
from app.database import engine
from app.liangmai.client import liangmai
from app.liangmai.parsing import emotion_for_date

log = logging.getLogger("emotion.service")


async def fetch_emotion_cycle(trade_date: str = None) -> dict:
    """拉取情绪周期数据 → emotion_cycle"""
    trade_date = trade_date or date.today().isoformat()

    result = await liangmai.call("anomaly_emotion_cycle", ttl=0)
    if not result.get("ok"):
        return {"ok": False, "msg": f"量脉调用失败: {result.get('msg')}"}

    data = result.get("data")
    if not data:
        return {"ok": True, "msg": "无情绪数据"}

    item = emotion_for_date(data, trade_date)
    if item is None:
        return {"ok": False, "dataMissing": True, "date": trade_date,
                "msg": "上游情绪序列不包含请求日期，未写入其他日期的数据"}

    # 解析情绪数据 (量脉 colNameList 映射)
    # 列: date1=日期 szbl=上涨比例 lbjs=连板数 ylgd=最高board zxgd=最低board
    #     dmqx=当日情绪分 drqx=? ztjs=涨停家数 dbcgl=封板率 dtjs=跌停家数 zbjs=炸板家数
    emotion_index = _float(item.get("dmqx", item.get("emotionIndex", item.get("emotion_index", item.get("score")))))
    raw_phase = item.get("drqx", item.get("emotionLevel", item.get("emotion_level", item.get("level", ""))))
    # 如果是数值，转换为阶段文字
    if isinstance(raw_phase, (int, float)):
        s = float(raw_phase)
        if s < 25:
            emotion_level = "冰点"
        elif s < 45:
            emotion_level = "修复"
        elif s < 65:
            emotion_level = "升温"
        elif s < 80:
            emotion_level = "高潮"
        else:
            emotion_level = "退潮"
    else:
        emotion_level = str(raw_phase) if raw_phase else ""
    rise_ratio = _float(item.get("szbl"))

    limit_up_count = _int(item.get("ztjs", item.get("limitUpCount", item.get("limit_up_count"))))
    limit_down_count = _int(item.get("dtjs", item.get("limitDownCount", item.get("limit_down_count"))))
    rise_count = _int(item.get("riseCount", item.get("rise_count", item.get("upNum"))))
    fall_count = _int(item.get("fallCount", item.get("fall_count", item.get("downNum"))))
    height_board = _int(item.get("ylgd", item.get("heightBoard", item.get("height_board", item.get("maxBoard")))))
    continue_count = _int(item.get("lbjs", item.get("continueCount", item.get("continue_count", item.get("lianban")))))
    broken_count = _int(item.get("zbjs", item.get("brokenCount", item.get("broken_count", item.get("zhapan")))))
    seal_rate = _float(item.get("dbcgl", item.get("sealRate", item.get("seal_rate"))))

    rows = {
        "trade_date": trade_date,
        "limit_up_count": limit_up_count,
        "limit_down_count": limit_down_count,
        "rise_count": rise_count,
        "fall_count": fall_count,
        "emotion_score": emotion_index,
        "cycle_phase": emotion_level,
        "height_board": height_board,
        "continue_count": continue_count,
        "broken_count": broken_count,
        "seal_rate": seal_rate,
        "avg_change_pct": _float(item.get("avgChangePct", item.get("avg_change_pct"))),
        "turnover_avg": _float(item.get("turnoverAvg", item.get("turnover_avg"))),
    }

    async with engine.begin() as conn:
        # UPSERT: 删除当日旧数据再插入
        await conn.execute(text("DELETE FROM emotion_cycle WHERE trade_date = :d"), {"d": trade_date})
        await conn.execute(text("""
            INSERT INTO emotion_cycle
                (trade_date, limit_up_count, limit_down_count, rise_count, fall_count,
                 emotion_score, cycle_phase, height_board, continue_count, broken_count,
                 seal_rate, avg_change_pct, turnover_avg)
            VALUES
                (:trade_date, :limit_up_count, :limit_down_count, :rise_count, :fall_count,
                 :emotion_score, :cycle_phase, :height_board, :continue_count, :broken_count,
                 :seal_rate, :avg_change_pct, :turnover_avg)
        """), rows)

    log.info(f"情绪周期写入: score={emotion_index}, phase={emotion_level}, 涨停={limit_up_count}, 跌停={limit_down_count}")
    return {"ok": True, "date": trade_date, "data": rows}


async def query_emotion(trade_date: str = None, days: int = 30) -> dict:
    """查询情绪周期（当日 + 近 N 天趋势）"""
    trade_date = trade_date or date.today().isoformat()
    async with engine.begin() as conn:
        # 当日
        today_result = await conn.execute(text(
            "SELECT * FROM emotion_cycle WHERE trade_date = :d"), {"d": trade_date})
        today = today_result.first()

        # 近 N 天趋势
        trend_result = await conn.execute(text("""
            SELECT * FROM emotion_cycle WHERE trade_date <= :d ORDER BY trade_date DESC LIMIT :l
        """), {"l": days, "d": trade_date})
        trend = [dict(row._mapping) for row in trend_result]

    return {
        "ok": True,
        "date": trade_date,
        "today": dict(today._mapping) if today else None,
        "trend": trend,
    }


async def query_emotion_summary(trade_date: str = None) -> dict:
    """情绪摘要：当前状态 + 连续天数 + 风险等级"""
    trade_date = trade_date or date.today().isoformat()
    async with engine.begin() as conn:
        # 最近 10 天数据
        result = await conn.execute(text("""
            SELECT trade_date, emotion_score, cycle_phase, limit_up_count, limit_down_count,
                   height_board, broken_count
            FROM emotion_cycle WHERE trade_date <= :d ORDER BY trade_date DESC LIMIT 10
        """), {"d": trade_date})
        rows = [dict(row._mapping) for row in result]

    if not rows:
        return {"ok": True, "date": trade_date, "summary": None}

    today = rows[0]
    score = today.get("emotion_score", 0) or 0

    # 计算连续天数
    days_above_50 = 0
    days_below_30 = 0
    for r in rows:
        s = r.get("emotion_score", 0) or 0
        if s >= 50:
            days_above_50 += 1
        else:
            break
    for r in rows:
        s = r.get("emotion_score", 0) or 0
        if s < 30:
            days_below_30 += 1
        else:
            break

    # 趋势判断
    if len(rows) >= 3:
        recent_scores = [r.get("emotion_score", 0) or 0 for r in rows[:3]]
        if recent_scores[0] > recent_scores[2]:
            trend = "rising"
        elif recent_scores[0] < recent_scores[2]:
            trend = "falling"
        else:
            trend = "stable"
    else:
        trend = "unknown"

    # 风险等级
    if score >= 80:
        risk = "high"
    elif score >= 60:
        risk = "medium"
    else:
        risk = "low"

    return {
        "ok": True,
        "date": trade_date,
        "emotion_score": score,
        "cycle_phase": today.get("cycle_phase", ""),
        "trend": trend,
        "days_above_50": days_above_50,
        "days_below_30": days_below_30,
        "risk_level": risk,
        "height_board": today.get("height_board", 0),
        "limit_up_count": today.get("limit_up_count", 0),
        "limit_down_count": today.get("limit_down_count", 0),
    }


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
