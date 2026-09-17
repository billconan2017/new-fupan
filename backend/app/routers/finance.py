from fastapi import APIRouter
from app.liangmai.client import liangmai

router = APIRouter(prefix="/api/finance", tags=["finance"])


@router.get("/profile/{code}")
async def company_profile(code: str):
    result = await liangmai.call("corp_profile", {"ts_code": code}, ttl=86400)
    return result


@router.get("/balance-sheet/{code}")
async def balance_sheet(code: str):
    result = await liangmai.call("finance_balance_sheet", {"full_code": code}, ttl=86400)
    return result


@router.get("/income/{code}")
async def income(code: str):
    result = await liangmai.call("finance_income_statement", {"full_code": code}, ttl=86400)
    return result


@router.get("/cashflow/{code}")
async def cashflow(code: str):
    result = await liangmai.call("finance_cashflow_statement", {"full_code": code}, ttl=86400)
    return result


@router.get("/holders/{code}")
async def holders(code: str):
    result = await liangmai.call("corp_top10_holders", {"ts_code": code}, ttl=86400)
    return result


@router.get("/dividend/{code}")
async def dividend(code: str):
    result = await liangmai.call("corp_dividend", {"ts_code": code}, ttl=86400)
    return result
