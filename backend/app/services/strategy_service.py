"""策略选股服务

多条件筛选、方案保存/读取/删除、历史回测、导出。
"""
import json
import logging
from datetime import date
from typing import Optional
from sqlalchemy import text
from app.database import engine

log = logging.getLogger("strategy.service")


async def screen_stocks(filters: dict, trade_date: str = None) -> dict:
    """
    多条件筛选选股

    filters 支持：
        min_consecutive: 最小连板数
        min_seal_amount: 最小封单金额
        min_turnover: 最小换手率
        max_turnover: 最大换手率
        min_amount: 最小成交额
        min_pct_chg: 最小涨跌幅
        max_pct_chg: 最大涨跌幅
        industry: 行业板块
        min_total_cap: 最小总市值
        max_total_cap: 最大总市值
        exclude_st: 是否剔除ST
        exclude_blacklist: 是否剔除黑名单
    """
    trade_date = trade_date or date.today().isoformat()
    conditions = ["lu.trade_date = :d"]
    params = {"d": trade_date}

    # 连板数
    if filters.get("min_consecutive"):
        conditions.append("lu.consecutive >= :min_consecutive")
        params["min_consecutive"] = int(filters["min_consecutive"])

    # 封单金额
    if filters.get("min_seal_amount"):
        conditions.append("lu.seal_amount >= :min_seal_amount")
        params["min_seal_amount"] = int(filters["min_seal_amount"])

    # 换手率
    if filters.get("min_turnover"):
        conditions.append("lu.turnover >= :min_turnover")
        params["min_turnover"] = float(filters["min_turnover"])
    if filters.get("max_turnover"):
        conditions.append("lu.turnover <= :max_turnover")
        params["max_turnover"] = float(filters["max_turnover"])

    # 成交额
    if filters.get("min_amount"):
        conditions.append("lu.amount >= :min_amount")
        params["min_amount"] = int(filters["min_amount"])

    # 涨跌幅
    if filters.get("min_pct_chg"):
        conditions.append("lu.pct_chg >= :min_pct_chg")
        params["min_pct_chg"] = float(filters["min_pct_chg"])
    if filters.get("max_pct_chg"):
        conditions.append("lu.pct_chg <= :max_pct_chg")
        params["max_pct_chg"] = float(filters["max_pct_chg"])

    # 行业
    if filters.get("industry"):
        conditions.append("lu.industry = :industry")
        params["industry"] = filters["industry"]

    # 总市值
    if filters.get("min_total_cap"):
        conditions.append("lu.total_cap >= :min_total_cap")
        params["min_total_cap"] = int(filters["min_total_cap"])
    if filters.get("max_total_cap"):
        conditions.append("lu.total_cap <= :max_total_cap")
        params["max_total_cap"] = int(filters["max_total_cap"])

    # ST剔除
    if filters.get("exclude_st"):
        conditions.append("sb.is_st = FALSE")

    # 黑名单过滤
    if filters.get("exclude_blacklist"):
        conditions.append("lu.code NOT IN (SELECT code FROM risk_blacklist WHERE status = 'active')")

    where = " AND ".join(conditions)

    # 主查询：从涨停池 + 强势股池联合筛选
    async with engine.begin() as conn:
        result = await conn.execute(text(f"""
            SELECT lu.code, lu.name, lu.price, lu.pct_chg, lu.amount, lu.turnover,
                   lu.consecutive, lu.seal_amount, lu.industry, lu.total_cap,
                   lu.first_seal_time, lu.last_seal_time,
                   COALESCE(cf.main_net, 0) as main_net,
                   COALESCE(cf.main_pct, 0) as main_pct
            FROM limit_up_pool lu
            LEFT JOIN stock_basic sb ON lu.code = sb.code
            LEFT JOIN capital_flow cf ON lu.code = cf.code AND cf.trade_date = lu.trade_date
            WHERE {where}
            ORDER BY lu.consecutive DESC, lu.seal_amount DESC
            LIMIT 200
        """), params)
        items = [dict(row._mapping) for row in result]

    # 如果涨停池结果不足，补充强势股
    if len(items) < 20:
        strong_conditions = ["sp.trade_date = :d"]
        strong_params = {"d": trade_date}

        if filters.get("min_pct_chg"):
            strong_conditions.append("sp.pct_chg >= :min_pct_chg")
            strong_params["min_pct_chg"] = float(filters["min_pct_chg"])
        if filters.get("industry"):
            strong_conditions.append("sp.industry = :industry")
            strong_params["industry"] = filters["industry"]
        if filters.get("min_amount"):
            strong_conditions.append("sp.amount >= :min_amount")
            strong_params["min_amount"] = int(filters["min_amount"])
        if filters.get("exclude_st"):
            strong_conditions.append("sb.is_st = FALSE")
        if filters.get("exclude_blacklist"):
            strong_conditions.append("sp.code NOT IN (SELECT code FROM risk_blacklist WHERE status = 'active')")

        strong_where = " AND ".join(strong_conditions)

        async with engine.begin() as conn:
            result = await conn.execute(text(f"""
                SELECT sp.code, sp.name, sp.price, sp.pct_chg, sp.amount, sp.turnover,
                       sp.industry, sp.volume_ratio, sp.amplitude,
                       COALESCE(cf.main_net, 0) as main_net,
                       COALESCE(cf.main_pct, 0) as main_pct
                FROM strong_pool sp
                LEFT JOIN stock_basic sb ON sp.code = sb.code
                LEFT JOIN capital_flow cf ON sp.code = cf.code AND cf.trade_date = sp.trade_date
                WHERE {strong_where}
                ORDER BY sp.pct_chg DESC
                LIMIT :limit
            """), {**strong_params, "limit": 200 - len(items)})
            strong_items = [dict(row._mapping) for row in result]

        # 去重合并
        existing_codes = {i["code"] for i in items}
        for si in strong_items:
            if si["code"] not in existing_codes:
                items.append(si)

    return {"ok": True, "date": trade_date, "count": len(items), "items": items}


async def save_strategy(name: str, filters: dict, trade_date: str = None, results: list = None) -> dict:
    """保存选股方案"""
    trade_date = trade_date or date.today().isoformat()
    results = results or []

    async with engine.begin() as conn:
        await conn.execute(text("""
            INSERT INTO strategy_record (strategy_name, trade_date, filters_json, result_json, result_count, created_at)
            VALUES (:name, :date, :filters, :results, :count, NOW())
        """), {
            "name": name,
            "date": trade_date,
            "filters": json.dumps(filters, ensure_ascii=False),
            "results": json.dumps(results, ensure_ascii=False),
            "count": len(results),
        })

    return {"ok": True, "name": name, "date": trade_date, "count": len(results)}


async def get_strategies(name: str = None, limit: int = 50) -> dict:
    """读取保存的方案"""
    conditions = []
    params = {"limit": limit}

    if name:
        conditions.append("strategy_name = :name")
        params["name"] = name

    where = " AND ".join(conditions) if conditions else "1=1"

    async with engine.begin() as conn:
        result = await conn.execute(text(f"""
            SELECT id, strategy_name, trade_date, filters_json, result_count, created_at
            FROM strategy_record WHERE {where}
            ORDER BY created_at DESC LIMIT :limit
        """), params)
        items = [dict(row._mapping) for row in result]

    return {"ok": True, "items": items}


async def get_strategy_detail(strategy_id: int) -> dict:
    """获取方案详情（含筛选条件和结果）"""
    async with engine.begin() as conn:
        result = await conn.execute(text(
            "SELECT * FROM strategy_record WHERE id = :id"), {"id": strategy_id})
        row = result.first()
        if not row:
            return {"ok": False, "msg": "方案不存在"}
        item = dict(row._mapping)
        # 解析 JSON
        item["filters"] = json.loads(item.get("filters_json") or "{}")
        item["results"] = json.loads(item.get("result_json") or "[]")

    return {"ok": True, "item": item}


async def delete_strategy(strategy_id: int) -> dict:
    """删除方案"""
    async with engine.begin() as conn:
        result = await conn.execute(text(
            "DELETE FROM strategy_record WHERE id = :id RETURNING id"), {"id": strategy_id})
        deleted = result.first()
    if deleted:
        return {"ok": True, "msg": "已删除"}
    return {"ok": False, "msg": "方案不存在"}


async def backtest_strategy(filters: dict, start_date: str, end_date: str = None) -> dict:
    """历史回测：在指定日期范围内执行选股"""
    end_date = end_date or start_date
    from datetime import datetime, timedelta

    dates = []
    d = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    while d <= end:
        if d.weekday() < 5:
            dates.append(d.isoformat())
        d += timedelta(days=1)

    results = {}
    for td in dates[:30]:  # 最多30天
        try:
            day_result = await screen_stocks(filters, trade_date=td)
            results[td] = {
                "count": day_result.get("count", 0),
                "items": day_result.get("items", [])[:10],  # 只保留前10
            }
        except Exception as e:
            results[td] = {"count": 0, "error": str(e)}

    return {"ok": True, "dates": list(results.keys()), "results": results}


async def export_stocks(filters: dict, trade_date: str = None) -> dict:
    """导出选股结果"""
    result = await screen_stocks(filters, trade_date)
    if not result.get("ok"):
        return result

    # 格式化为CSV-friendly
    items = result.get("items", [])
    csv_rows = []
    for item in items:
        csv_rows.append({
            "代码": item.get("code", ""),
            "名称": item.get("name", ""),
            "价格": item.get("price", ""),
            "涨幅%": item.get("pct_chg", ""),
            "成交额": item.get("amount", ""),
            "换手率%": item.get("turnover", ""),
            "连板数": item.get("consecutive", ""),
            "封单金额": item.get("seal_amount", ""),
            "行业": item.get("industry", ""),
            "主力净流入": item.get("main_net", ""),
        })

    return {"ok": True, "date": trade_date or date.today().isoformat(), "count": len(csv_rows), "export": csv_rows}
