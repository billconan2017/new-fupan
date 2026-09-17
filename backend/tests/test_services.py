from unittest.mock import AsyncMock, MagicMock
from contextlib import asynccontextmanager
import pytest
from sqlalchemy import text
from app.services import emotion_service, pool_service, dragon_service
from app.routers.kline import _fetch_and_persist


class FakeEngine:
    def __init__(self): self.calls=[]
    @asynccontextmanager
    async def begin(self): yield self
    async def execute(self, statement, params):
        # Validate every SQL bind is present, catching the old LHB INSERT defect.
        required=set(statement._bindparams)
        for row in params if isinstance(params,list) else [params]:
            assert required <= set(row), required-set(row)
        self.calls.append((str(statement),params))


async def test_emotion_missing_day_never_writes(monkeypatch):
    engine=FakeEngine();monkeypatch.setattr(emotion_service,'engine',engine)
    monkeypatch.setattr(emotion_service.liangmai,'call',AsyncMock(return_value={'ok':True,'data':{'colNameList':['date1','ztjs'],'contentList':[[20260916,89]]}}))
    r=await emotion_service.fetch_emotion_cycle('2026-09-15')
    assert not r['ok'] and r['dataMissing'] and not engine.calls


async def test_pool_mixed_case_and_lhb_bindings(monkeypatch):
    engine=FakeEngine()
    monkeypatch.setattr(pool_service,'engine',engine)
    await pool_service._insert_limit_up('2026-09-16',[{'dm':'000001','Mc':'平安银行','Lbc':3}])
    assert engine.calls[-1][1][0]['name']=='平安银行'
    assert engine.calls[-1][1][0]['consecutive']==3
    monkeypatch.setattr(dragon_service,'engine',engine)
    await dragon_service._insert_dragon_tiger('2026-09-16',[{'thsCode':'000001','name':'平安银行','chg':'2','buyAmount':'10','sellAmount':'3','close':'12'}])
    row=engine.calls[-1][1][0]
    assert row['net_amount']==70000 and row['buy_amount']==100000 and row['close']==12


async def test_kline_persists_t_date_and_forwards_range(monkeypatch):
    from app.routers import kline
    engine=FakeEngine();monkeypatch.setattr(kline,'engine',engine)
    call=AsyncMock(return_value={'ok':True,'data':[{'t':'2026-09-16','o':11,'h':13,'l':10,'c':12}]})
    monkeypatch.setattr(kline.liangmai,'call',call)
    await _fetch_and_persist('000001','day',120,'2026-09-01','2026-09-16')
    p=call.call_args.args[1]
    assert p['st']=='20260901' and p['et']=='20260916' and p['interval']=='d'
    assert engine.calls[-1][1]['td']=='2026-09-16'


async def test_stock_names_and_flat_youzi(monkeypatch):
    from app.services import stock_basic_service
    engine=FakeEngine();monkeypatch.setattr(stock_basic_service,'engine',engine)
    await stock_basic_service._upsert_stock_basic([{'dm':'000001','mc':'平安银行','jys':'sz'}])
    assert engine.calls[-1][1]['name']=='平安银行'
    assert engine.calls[-1][1]['total_cap'] is None
    rows=dragon_service.normalize_youzi([{'yzmc':'测试席位','gpdm':'000001','gpmc':'平安银行','mrje':'100','mcje':'20','rq':'2026-09-16'}],'2026-09-16')
    assert rows[0]['buy_list'][0]['amount']==100
    assert rows[0]['sell_list'][0]['amount']==20
    assert not dragon_service.normalize_youzi([{'yzmc':'测试','gpdm':'000001','rq':'2026-09-15'}],'2026-09-16')
