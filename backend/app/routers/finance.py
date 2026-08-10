from fastapi import APIRouter
from app.liangmai.client import liangmai

router = APIRouter(prefix="/api/finance", tags=["finance"])


@router.get("/profile/{code}")
async def company_profile(code: str):
    result = await liangmai.call("company_profile", {"ts_code": code}, ttl=86400)
    return result


@router.get("/balance-sheet/{code}")
async def balance_sheet(code: str):
    result = await liangmai.call("fin_balance_sheet", {"ts_code": code}, ttl=86400)
    return result


@router.get("/income/{code}")
async def income(code: str):
    result = await liangmai.call("fin_income_statement", {"ts_code": code}, ttl=86400)
    return result


@router.get("/cashflow/{code}")
async def cashflow(code: str):
    result = await liangmai.call("fin_cashflow_statement", {"ts_code": code}, ttl=86400)
    return result


@router.get("/holders/{code}")
async def holders(code: str):
    result = await liangmai.call("company_holders_top10", {"ts_code": code}, ttl=86400)
    return result


@router.get("/dividend/{code}")
async def dividend(code: str):
    result = await liangmai.call("company_dividend", {"ts_code": code}, ttl=86400)
    return result
