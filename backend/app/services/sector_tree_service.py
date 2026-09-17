"""板块树服务 — sector_tree 表维护

从量脉拉取板块行业树，写入 sector_tree 表。
"""
import logging
from sqlalchemy import text
from app.database import engine
from app.liangmai.client import liangmai

log = logging.getLogger("sector_tree.service")


async def update_sector_tree() -> dict:
    """更新板块行业树（量脉唯一源）"""
    result = await liangmai.call("sector_catalog", ttl=3600)
    if result.get("ok"):
        data = result.get("data", [])
        items = data if isinstance(data, list) else data.get("list", [])
        if items:
            count = await _upsert_sector_tree(items, source="liangmai", level=1)
            return {"ok": True, "count": count, "source": "liangmai"}

    return {"ok": False, "msg": "板块树拉取失败"}


async def _upsert_sector_tree(items: list, source: str = "unknown", level: int = 1, prefix: str = "") -> int:
    """批量写入/更新 sector_tree"""
    rows = []
    for s in items:
        code = s.get("code", s.get("c", s.get("dm", s.get("sector_code", ""))))
        if not code:
            continue
        if prefix and not code.startswith(prefix):
            continue
        rows.append({
            "sector_code": code,
            "sector_name": s.get("name", s.get("n", s.get("sector_name", s.get("mc", "")))),
            "parent_code": s.get("parent_code", s.get("parent", "")),
            "level": level,
            "stock_count": _int(s.get("stock_count", s.get("count", 0))),
            "source": source,
        })

    if not rows:
        return 0

    async with engine.begin() as conn:
        for r in rows:
            await conn.execute(text("""
                INSERT INTO sector_tree (sector_code, sector_name, parent_code, level, stock_count, source, updated_at)
                VALUES (:sector_code, :sector_name, :parent_code, :level, :stock_count, :source, NOW())
                ON CONFLICT (sector_code) DO UPDATE SET
                    sector_name = EXCLUDED.sector_name,
                    parent_code = EXCLUDED.parent_code,
                    level = EXCLUDED.level,
                    stock_count = EXCLUDED.stock_count,
                    source = EXCLUDED.source,
                    updated_at = NOW()
            """), r)

    log.info(f"sector_tree 写入: {len(rows)} 条 (source={source}, level={level})")
    return len(rows)


def _int(v) -> int:
    try:
        return int(float(v)) if v else 0
    except (ValueError, TypeError):
        return 0


# ── 查询接口 ──

async def query_sector_tree(source: str = None, level: int = None) -> dict:
    """查询板块树"""
    conditions = []
    params = {}

    if source:
        conditions.append("source = :source")
        params["source"] = source
    if level is not None:
        conditions.append("level = :level")
        params["level"] = level

    where = " AND ".join(conditions) if conditions else "1=1"

    async with engine.begin() as conn:
        result = await conn.execute(text(
            f"SELECT * FROM sector_tree WHERE {where} ORDER BY source, sector_code"
        ), params)
        items = [dict(row._mapping) for row in result]

    return {"ok": True, "count": len(items), "items": items}


async def get_valid_bk_codes() -> list[str]:
    """获取合法板块代码列表"""
    async with engine.begin() as conn:
        result = await conn.execute(text(
            "SELECT sector_code FROM sector_tree WHERE source IN ('881','884') LIMIT 200"
        ))
        return [row[0] for row in result]
