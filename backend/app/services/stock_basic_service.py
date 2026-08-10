"""个股基础信息服务 — stock_basic 表维护

从量脉拉取全市场股票基础信息，写入 stock_basic 表。
"""
import logging
from datetime import date
from sqlalchemy import text
from app.database import engine
from app.liangmai.client import liangmai

log = logging.getLogger("stock_basic.service")


async def update_stock_basic() -> dict:
    """更新全市场个股基础信息（量脉唯一源）"""
    result = await liangmai.call("stock_list", ttl=3600)
    if result.get("ok"):
        data = result.get("data", [])
        items = data if isinstance(data, list) else data.get("list", [])
        if items:
            count = await _upsert_stock_basic(items, source="liangmai")
            return {"ok": True, "count": count, "source": "liangmai"}

    return {"ok": False, "msg": "股票基础信息拉取失败"}


async def _upsert_stock_basic(items: list, source: str = "unknown") -> int:
    """批量写入/更新 stock_basic"""
    rows = []
    for s in items:
        code = s.get("code", s.get("c", s.get("dm", s.get("ts_code", ""))))
        if not code:
            continue
        code = code.split(".")[0]
        rows.append({
            "code": code,
            "name": s.get("name", s.get("n", s.get("name", ""))),
            "market": _detect_market(code),
            "industry": s.get("industry", s.get("industry_name", s.get("hy", ""))),
            "concept": s.get("concept", s.get("concept_name", "")),
            "total_cap": _int(s.get("total_cap", s.get("total_mv", s.get("totalMarketValue", 0)))),
            "circulating_cap": _int(s.get("circulating_cap", s.get("circ_mv", s.get("floatMarketValue", 0)))),
            "list_date": s.get("list_date", s.get("startDate", "")),
            "is_st": bool(s.get("is_st", s.get("isST", False))),
            "status": "active",
        })

    if not rows:
        return 0

    async with engine.begin() as conn:
        for r in rows:
            await conn.execute(text("""
                INSERT INTO stock_basic (code, name, market, industry, concept, total_cap, circulating_cap, list_date, is_st, status, updated_at)
                VALUES (:code, :name, :market, :industry, :concept, :total_cap, :circulating_cap, :list_date, :is_st, :status, NOW())
                ON CONFLICT (code) DO UPDATE SET
                    name = EXCLUDED.name,
                    market = EXCLUDED.market,
                    industry = EXCLUDED.industry,
                    concept = EXCLUDED.concept,
                    total_cap = EXCLUDED.total_cap,
                    circulating_cap = EXCLUDED.circulating_cap,
                    is_st = EXCLUDED.is_st,
                    updated_at = NOW()
            """), r)

    log.info(f"stock_basic 写入: {len(rows)} 条 (source={source})")
    return len(rows)


def _detect_market(code: str) -> str:
    if code.startswith("6"):
        return "sh"
    elif code.startswith(("0", "3")):
        return "sz"
    elif code.startswith(("4", "8")):
        return "bj"
    return "unknown"


def _int(v) -> int:
    try:
        return int(float(v)) if v else 0
    except (ValueError, TypeError):
        return 0


# ── 查询接口 ──

async def query_stock_basic(code: str = None, industry: str = None,
                             is_st: bool = None, limit: int = 100) -> dict:
    """查询个股基础信息"""
    conditions = ["status = 'active'"]
    params = {}

    if code:
        conditions.append("code = :code")
        params["code"] = code
    if industry:
        conditions.append("industry = :industry")
        params["industry"] = industry
    if is_st is not None:
        conditions.append("is_st = :is_st")
        params["is_st"] = is_st

    where = " AND ".join(conditions)
    params["limit"] = limit

    async with engine.begin() as conn:
        result = await conn.execute(text(
            f"SELECT * FROM stock_basic WHERE {where} ORDER BY code LIMIT :limit"
        ), params)
        items = [dict(row._mapping) for row in result]

    return {"ok": True, "count": len(items), "items": items}
