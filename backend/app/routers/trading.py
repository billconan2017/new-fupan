"""实盘交易 API"""
from fastapi import APIRouter, Query, Body
from app.services.trading_service import (
    add_account, update_account, delete_account, list_accounts,
    sync_positions, get_positions, get_account_summary,
    place_order, cancel_order, cancel_all_orders, clear_positions,
    get_orders, get_trade_history, get_monthly_pnl,
    add_blacklist, remove_blacklist, list_blacklist,
    get_trade_review,
)

router = APIRouter(prefix="/api/trading", tags=["trading"])


# ── 账户管理 ──

@router.get("/accounts")
async def api_list_accounts():
    """列出账户"""
    return await list_accounts()


@router.post("/accounts")
async def api_add_account(data: dict = Body(...)):
    """新增账户"""
    return await add_account(data)


@router.put("/accounts/{account_id}")
async def api_update_account(account_id: int, data: dict = Body(...)):
    """编辑账户"""
    return await update_account(account_id, data)


@router.delete("/accounts/{account_id}")
async def api_delete_account(account_id: int):
    """删除账户"""
    return await delete_account(account_id)


@router.get("/accounts/{account_id}/summary")
async def api_account_summary(account_id: int, date: str = Query(None)):
    """账户资产汇总"""
    return await get_account_summary(account_id, date)


# ── 持仓管理 ──

@router.get("/positions")
async def api_get_positions(account_id: int = Query(None), date: str = Query(None)):
    """查询持仓"""
    return await get_positions(account_id, date)


@router.post("/positions/sync")
async def api_sync_positions(account_id: int = Query(...), positions: list = Body(...)):
    """同步持仓"""
    return await sync_positions(account_id, positions)


# ── 委托下单 ──

@router.post("/orders")
async def api_place_order(data: dict = Body(...)):
    """下单"""
    return await place_order(data)


@router.delete("/orders/{order_id}")
async def api_cancel_order(order_id: int):
    """撤单"""
    return await cancel_order(order_id)


@router.delete("/orders")
async def api_cancel_all(account_id: int = Query(...), date: str = Query(None)):
    """批量撤单"""
    return await cancel_all_orders(account_id, date)


@router.post("/clear")
async def api_clear(account_id: int = Query(...)):
    """一键清仓"""
    return await clear_positions(account_id)


@router.get("/orders")
async def api_get_orders(
    account_id: int = Query(None),
    date: str = Query(None),
    status: str = Query(None),
    limit: int = Query(100),
):
    """查询委托"""
    return await get_orders(account_id, date, status, limit)


@router.get("/trades")
async def api_trade_history(account_id: int = Query(None), days: int = Query(30)):
    """成交历史"""
    return await get_trade_history(account_id, days)


@router.get("/pnl/monthly")
async def api_monthly_pnl(
    account_id: int = Query(...),
    year: int = Query(None),
    month: int = Query(None),
):
    """月度盈亏"""
    return await get_monthly_pnl(account_id, year, month)


@router.get("/review")
async def api_trade_review(account_id: int = Query(...), date: str = Query(None)):
    """交易复盘"""
    return await get_trade_review(account_id, date)


# ── 风控设置 ──

@router.post("/blacklist")
async def api_add_blacklist(
    code: str = Query(...),
    name: str = Query(""),
    reason: str = Query(""),
):
    """加入黑名单"""
    return await add_blacklist(code, name, reason)


@router.delete("/blacklist/{code}")
async def api_remove_blacklist(code: str):
    """移出黑名单"""
    return await remove_blacklist(code)


@router.get("/blacklist")
async def api_list_blacklist():
    """查询黑名单"""
    return await list_blacklist()
