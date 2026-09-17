"""实盘交易服务

账户管理、持仓同步、委托下单、风控拦截、交易日志。
"""
import json
import logging
from datetime import datetime, date
from typing import Optional
from sqlalchemy import text
from app.database import engine

log = logging.getLogger("trading.service")


# ══════════════════════════════════════════════
# 账户管理
# ══════════════════════════════════════════════

async def add_account(data: dict) -> dict:
    """新增账户"""
    async with engine.begin() as conn:
        # 检查重名
        exists = await conn.execute(text(
            "SELECT id FROM account_info WHERE account_name = :name"), {"name": data["account_name"]})
        if exists.first():
            return {"ok": False, "msg": "账户名已存在"}

        await conn.execute(text("""
            INSERT INTO account_info (account_name, broker, account_type, api_key, api_secret,
                                      initial_capital, status, remark)
            VALUES (:account_name, :broker, :account_type, :api_key, :api_secret,
                    :initial_capital, :status, :remark)
        """), {
            "account_name": data.get("account_name"),
            "broker": data.get("broker", ""),
            "account_type": data.get("account_type", "stock"),
            "api_key": data.get("api_key", ""),
            "api_secret": data.get("api_secret", ""),
            "initial_capital": data.get("initial_capital", 0),
            "status": data.get("status", "active"),
            "remark": data.get("remark", ""),
        })

    return {"ok": True, "msg": "账户已添加"}


async def update_account(account_id: int, data: dict) -> dict:
    """编辑账户"""
    fields = []
    params = {"id": account_id}
    for key in ["account_name", "broker", "account_type", "api_key", "api_secret",
                 "initial_capital", "status", "remark"]:
        if key in data:
            fields.append(f"{key} = :{key}")
            params[key] = data[key]

    if not fields:
        return {"ok": False, "msg": "无更新字段"}

    fields.append("updated_at = NOW()")
    set_clause = ", ".join(fields)

    async with engine.begin() as conn:
        await conn.execute(text(f"UPDATE account_info SET {set_clause} WHERE id = :id"), params)

    return {"ok": True, "msg": "已更新"}


async def delete_account(account_id: int) -> dict:
    """删除账户"""
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM account_info WHERE id = :id"), {"id": account_id})
    return {"ok": True, "msg": "已删除"}


async def list_accounts() -> dict:
    """列出所有账户"""
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT id, account_name, broker, account_type, initial_capital, status, remark FROM account_info ORDER BY id"))
        items = [dict(row._mapping) for row in result]
    return {"ok": True, "items": items}


# ══════════════════════════════════════════════
# 持仓管理
# ══════════════════════════════════════════════

async def sync_positions(account_id: int, positions: list) -> dict:
    """同步持仓（一键覆盖）"""
    trade_date = date.today().isoformat()

    async with engine.begin() as conn:
        # 清除当日旧持仓
        await conn.execute(text(
            "DELETE FROM position_record WHERE account_id = :aid AND trade_date = :d"),
            {"aid": account_id, "d": trade_date})

        # 写入新持仓
        for pos in positions:
            await conn.execute(text("""
                INSERT INTO position_record (account_id, trade_date, code, name, quantity,
                    available_qty, cost_price, current_price, market_value, profit, profit_pct)
                VALUES (:account_id, :trade_date, :code, :name, :quantity,
                    :available_qty, :cost_price, :current_price, :market_value, :profit, :profit_pct)
            """), {
                "account_id": account_id,
                "trade_date": trade_date,
                "code": pos.get("code"),
                "name": pos.get("name", ""),
                "quantity": pos.get("quantity", 0),
                "available_qty": pos.get("available_qty", pos.get("quantity", 0)),
                "cost_price": pos.get("cost_price", 0),
                "current_price": pos.get("current_price", 0),
                "market_value": pos.get("market_value", 0),
                "profit": pos.get("profit", 0),
                "profit_pct": pos.get("profit_pct", 0),
            })

    return {"ok": True, "count": len(positions), "date": trade_date}


async def get_positions(account_id: int = None, trade_date: str = None) -> dict:
    """查询持仓"""
    trade_date = trade_date or date.today().isoformat()
    conditions = ["trade_date = :d"]
    params = {"d": trade_date}

    if account_id:
        conditions.append("account_id = :aid")
        params["aid"] = account_id

    where = " AND ".join(conditions)

    async with engine.begin() as conn:
        result = await conn.execute(text(
            f"SELECT * FROM position_record WHERE {where} ORDER BY market_value DESC"), params)
        items = [dict(row._mapping) for row in result]

    return {"ok": True, "date": trade_date, "items": items, "count": len(items)}


async def get_account_summary(account_id: int, trade_date: str = None) -> dict:
    """账户资产汇总"""
    trade_date = trade_date or date.today().isoformat()

    async with engine.begin() as conn:
        # 账户信息
        acc_result = await conn.execute(text(
            "SELECT * FROM account_info WHERE id = :id"), {"id": account_id})
        account = acc_result.first()
        if not account:
            return {"ok": False, "msg": "账户不存在"}
        acc = dict(account._mapping)

        # 当日持仓
        pos_result = await conn.execute(text(
            "SELECT * FROM position_record WHERE account_id = :aid AND trade_date = :d"),
            {"aid": account_id, "d": trade_date})
        positions = [dict(row._mapping) for row in pos_result]

        # 汇总
        total_market_value = sum(p.get("market_value", 0) or 0 for p in positions)
        total_profit = sum(p.get("profit", 0) or 0 for p in positions)
        initial_capital = acc.get("initial_capital", 0) or 0

    return {
        "ok": True,
        "account": acc,
        "positions": positions,
        "summary": {
            "initial_capital": initial_capital,
            "total_market_value": total_market_value,
            "total_profit": total_profit,
            "total_assets": initial_capital + total_profit,
            "position_count": len(positions),
        },
    }


# ══════════════════════════════════════════════
# 委托下单
# ══════════════════════════════════════════════

async def place_order(data: dict) -> dict:
    """下单（含风控拦截）"""
    trade_date = date.today().isoformat()
    account_id = data.get("account_id")
    code = data.get("code")
    direction = data.get("direction")  # buy/sell

    if not account_id or not code or not direction:
        return {"ok": False, "msg": "缺少必填参数: account_id, code, direction"}

    # ── 风控检查 ──
    risk_msg = await check_risk(data)
    if risk_msg:
        return {"ok": False, "msg": f"风控拦截: {risk_msg}"}

    # 写入委托记录
    async with engine.begin() as conn:
        await conn.execute(text("""
            INSERT INTO order_record (account_id, trade_date, order_time, code, name, direction,
                order_type, price, quantity, status, trigger_price, trigger_type, remark)
            VALUES (:account_id, :trade_date, NOW(), :code, :name, :direction,
                :order_type, :price, :quantity, :status, :trigger_price, :trigger_type, :remark)
        """), {
            "account_id": account_id,
            "trade_date": trade_date,
            "code": code,
            "name": data.get("name", ""),
            "direction": direction,
            "order_type": data.get("order_type", "limit"),
            "price": data.get("price", 0),
            "quantity": data.get("quantity", 0),
            "status": "pending",
            "trigger_price": data.get("trigger_price"),
            "trigger_type": data.get("trigger_type"),
            "remark": data.get("remark", ""),
        })

    return {"ok": True, "msg": "已保存本地委托记录，未发送券商", "execution_mode": "local_record", "date": trade_date}


async def cancel_order(order_id: int) -> dict:
    """撤单"""
    async with engine.begin() as conn:
        result = await conn.execute(text(
            "UPDATE order_record SET status = 'cancelled' WHERE id = :id AND status = 'pending' RETURNING id"),
            {"id": order_id})
        if not result.first():
            return {"ok": False, "msg": "委托不存在或已成交"}
    return {"ok": True, "msg": "已撤单"}


async def cancel_all_orders(account_id: int, trade_date: str = None) -> dict:
    """批量撤单"""
    trade_date = trade_date or date.today().isoformat()
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            UPDATE order_record SET status = 'cancelled'
            WHERE account_id = :aid AND trade_date = :d AND status = 'pending'
        """), {"aid": account_id, "d": trade_date})
    return {"ok": True, "msg": f"已撤销全部挂单"}


async def clear_positions(account_id: int) -> dict:
    """一键清仓"""
    trade_date = date.today().isoformat()
    async with engine.begin() as conn:
        # 获取当前持仓
        result = await conn.execute(text(
            "SELECT * FROM position_record WHERE account_id = :aid AND trade_date = :d"),
            {"aid": account_id, "d": trade_date})
        positions = [dict(row._mapping) for row in result]

        # 为每只股票创建卖出委托
        for pos in positions:
            await conn.execute(text("""
                INSERT INTO order_record (account_id, trade_date, order_time, code, name, direction,
                    order_type, price, quantity, status)
                VALUES (:aid, :d, NOW(), :code, :name, 'sell', 'market', :price, :qty, 'pending')
            """), {
                "aid": account_id, "d": trade_date,
                "code": pos["code"], "name": pos.get("name", ""),
                "price": pos.get("current_price", 0), "qty": pos.get("quantity", 0),
            })

    return {"ok": True, "msg": f"已提交 {len(positions)} 笔清仓委托", "count": len(positions)}


async def get_orders(account_id: int = None, trade_date: str = None,
                     status: str = None, limit: int = 100) -> dict:
    """查询委托记录"""
    trade_date = trade_date or date.today().isoformat()
    conditions = ["trade_date = :d"]
    params = {"d": trade_date, "limit": limit}

    if account_id:
        conditions.append("account_id = :aid")
        params["aid"] = account_id
    if status:
        conditions.append("status = :status")
        params["status"] = status

    where = " AND ".join(conditions)

    async with engine.begin() as conn:
        result = await conn.execute(text(
            f"SELECT * FROM order_record WHERE {where} ORDER BY created_at DESC LIMIT :limit"), params)
        items = [dict(row._mapping) for row in result]

    return {"ok": True, "date": trade_date, "items": items, "count": len(items)}


async def get_trade_history(account_id: int = None, days: int = 30) -> dict:
    """成交历史"""
    conditions = ["status IN ('filled', 'partial')"]
    params = {"limit": days * 50}

    if account_id:
        conditions.append("account_id = :aid")
        params["aid"] = account_id

    where = " AND ".join(conditions)

    async with engine.begin() as conn:
        result = await conn.execute(text(f"""
            SELECT * FROM order_record WHERE {where}
            ORDER BY trade_date DESC, created_at DESC LIMIT :limit
        """), params)
        items = [dict(row._mapping) for row in result]

    return {"ok": True, "items": items, "count": len(items)}


async def get_monthly_pnl(account_id: int, year: int = None, month: int = None) -> dict:
    """月度盈亏统计"""
    now = datetime.now()
    year = year or now.year
    month = month or now.month
    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{month + 1:02d}-01"

    async with engine.begin() as conn:
        # 已实现盈亏
        result = await conn.execute(text("""
            SELECT trade_date, code, name, direction, filled_qty, filled_price, filled_amount
            FROM order_record
            WHERE account_id = :aid AND status IN ('filled', 'partial')
              AND trade_date >= :start AND trade_date < :end
            ORDER BY trade_date
        """), {"aid": account_id, "start": start_date, "end": end_date})
        trades = [dict(row._mapping) for row in result]

    # 统计
    buy_amount = sum(t.get("filled_amount", 0) or 0 for t in trades if t.get("direction") == "buy")
    sell_amount = sum(t.get("filled_amount", 0) or 0 for t in trades if t.get("direction") == "sell")
    trade_count = len(trades)

    return {
        "ok": True,
        "year": year,
        "month": month,
        "buy_amount": buy_amount,
        "sell_amount": sell_amount,
        "net_amount": sell_amount - buy_amount,
        "trade_count": trade_count,
        "trades": trades,
    }


# ══════════════════════════════════════════════
# 风控检查
# ══════════════════════════════════════════════

async def check_risk(order_data: dict) -> Optional[str]:
    """
    风控拦截检查

    返回 None = 通过，返回字符串 = 拦截原因
    """
    code = order_data.get("code", "")
    direction = order_data.get("direction", "buy")
    account_id = order_data.get("account_id")

    if direction != "buy":
        return None  # 卖出不拦截

    # 1. 黑名单检查
    async with engine.begin() as conn:
        bl_result = await conn.execute(text(
            "SELECT reason FROM risk_blacklist WHERE code = :code AND status = 'active'"),
            {"code": code})
        bl = bl_result.first()
        if bl:
            return f"该股在黑名单中: {bl[0]}"

    # 2. 总仓位上限检查
    if account_id:
        trade_date = date.today().isoformat()
        async with engine.begin() as conn:
            # 账户信息
            acc_result = await conn.execute(text(
                "SELECT initial_capital FROM account_info WHERE id = :id"), {"id": account_id})
            acc = acc_result.first()
            if not acc:
                return "账户不存在"

            initial = acc[0] or 0
            if initial <= 0:
                return "账户初始资金未设置"

            # 当前持仓市值
            pos_result = await conn.execute(text("""
                SELECT COALESCE(SUM(market_value), 0) as total_mv
                FROM position_record WHERE account_id = :aid AND trade_date = :d
            """), {"aid": account_id, "d": trade_date})
            total_mv = pos_result.scalar() or 0

            # 仓位比例上限90%
            if total_mv > initial * 0.9:
                return f"总仓位已达{total_mv / initial * 100:.1f}%，超过90%上限"

            # 3. 单票最大持仓比例20%
            qty = order_data.get("quantity", 0)
            price = order_data.get("price", 0)
            order_value = qty * price
            # 获取该股当前持仓
            stock_pos = await conn.execute(text("""
                SELECT COALESCE(SUM(market_value), 0) as mv
                FROM position_record WHERE account_id = :aid AND trade_date = :d AND code = :code
            """), {"aid": account_id, "d": trade_date, "code": code})
            current_mv = stock_pos.scalar() or 0
            if (current_mv + order_value) > initial * 0.2:
                return f"单票持仓比例将超过20%上限 (当前: {current_mv / initial * 100:.1f}%)"

    return None  # 通过


async def add_blacklist(code: str, name: str = "", reason: str = "") -> dict:
    """加入黑名单"""
    async with engine.begin() as conn:
        await conn.execute(text("""
            INSERT INTO risk_blacklist (code, name, reason, added_date, status, created_at)
            VALUES (:code, :name, :reason, :date, 'active', NOW())
            ON CONFLICT (code) DO UPDATE SET
                name = EXCLUDED.name,
                reason = EXCLUDED.reason,
                added_date = EXCLUDED.added_date,
                status = 'active'
        """), {
            "code": code,
            "name": name,
            "reason": reason,
            "date": date.today().isoformat(),
        })
    return {"ok": True, "msg": f"{code} 已加入黑名单"}


async def remove_blacklist(code: str) -> dict:
    """移出黑名单"""
    async with engine.begin() as conn:
        await conn.execute(text("""
            UPDATE risk_blacklist SET status = 'removed', removed_date = :date
            WHERE code = :code AND status = 'active'
        """), {"code": code, "date": date.today().isoformat()})
    return {"ok": True, "msg": f"{code} 已移出黑名单"}


async def list_blacklist() -> dict:
    """查询黑名单"""
    async with engine.begin() as conn:
        result = await conn.execute(text(
            "SELECT * FROM risk_blacklist WHERE status = 'active' ORDER BY created_at DESC"))
        items = [dict(row._mapping) for row in result]
    return {"ok": True, "items": items, "count": len(items)}


# ══════════════════════════════════════════════
# 交易复盘
# ══════════════════════════════════════════════

async def get_trade_review(account_id: int, trade_date: str = None) -> dict:
    """交易复盘明细"""
    trade_date = trade_date or date.today().isoformat()

    async with engine.begin() as conn:
        # 当日委托
        orders = await conn.execute(text("""
            SELECT * FROM order_record WHERE account_id = :aid AND trade_date = :d
            ORDER BY created_at
        """), {"aid": account_id, "d": trade_date})
        order_list = [dict(row._mapping) for row in orders]

        # 当日持仓
        positions = await conn.execute(text("""
            SELECT * FROM position_record WHERE account_id = :aid AND trade_date = :d
        """), {"aid": account_id, "d": trade_date})
        pos_list = [dict(row._mapping) for row in positions]

    # 统计
    buy_count = sum(1 for o in order_list if o.get("direction") == "buy")
    sell_count = sum(1 for o in order_list if o.get("direction") == "sell")
    total_profit = sum(p.get("profit", 0) or 0 for p in pos_list)

    return {
        "ok": True,
        "date": trade_date,
        "orders": order_list,
        "positions": pos_list,
        "summary": {
            "buy_count": buy_count,
            "sell_count": sell_count,
            "position_count": len(pos_list),
            "total_profit": total_profit,
        },
    }
