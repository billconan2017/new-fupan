"""数据源中枢路由 — 两层查询 (本地PG → 量脉)

强制两层查询逻辑，所有业务 service 统一调用本路由：
  ① 第一层：本地 PostgreSQL → 有数据直接返回
  ② 第二层：量脉网关 → 成功则入库并返回
  ③ 两层全失败 → 标准化提示，不抛原始堆栈

规则：无本地数据时仅调用量脉拉取并持久化入库，不向其他外网数据源请求。
"""
import logging
import time
from datetime import datetime, date
from typing import Any, Optional, Callable, Awaitable
from sqlalchemy import text
from app.database import engine
from app.liangmai.client import liangmai
from app.config import get_settings

log = logging.getLogger("datasource")
settings = get_settings()


class CircuitBreaker:
    """量脉熔断器（仅告警，不切源）"""

    def __init__(self, threshold: int = 3, reset_hour: int = 0):
        self.threshold = threshold
        self.reset_hour = reset_hour
        self._consecutive_failures = 0
        self._tripped = False
        self._tripped_at: Optional[float] = None
        self._last_failure_msg = ""

    @property
    def is_tripped(self) -> bool:
        """检查熔断状态，凌晨自动恢复"""
        if not self._tripped:
            return False
        now = datetime.now()
        if now.hour == self.reset_hour and self._tripped_at:
            tripped_dt = datetime.fromtimestamp(self._tripped_at)
            if tripped_dt.date() < now.date():
                log.info("[熔断] 凌晨自动恢复量脉源")
                self.reset()
                return False
        return True

    def record_success(self):
        self._consecutive_failures = 0
        if self._tripped:
            log.info("[熔断] 量脉恢复正常，解除熔断")
            self.reset()

    def record_failure(self, msg: str = ""):
        self._consecutive_failures += 1
        self._last_failure_msg = msg
        if self._consecutive_failures >= self.threshold and not self._tripped:
            self._tripped = True
            self._tripped_at = time.time()
            log.warning(f"[熔断] 量脉连续{self._consecutive_failures}次失败，暂停拉取: {msg}")

    def reset(self):
        self._consecutive_failures = 0
        self._tripped = False
        self._tripped_at = None
        self._last_failure_msg = ""

    def get_status(self) -> dict:
        return {
            "tripped": self._tripped,
            "consecutive_failures": self._consecutive_failures,
            "threshold": self.threshold,
            "last_failure_msg": self._last_failure_msg,
            "tripped_at": self._tripped_at,
        }


class DataSourceRouter:
    """
    统一数据源路由：本地DB → 量脉（仅两层，无外网兜底）
    """

    def __init__(self):
        self._circuit = CircuitBreaker(
            threshold=settings.circuit_breaker_threshold,
            reset_hour=settings.circuit_breaker_reset_hour,
        )
        self._stats = {
            "total": 0,
            "local_hit": 0,
            "liangmai_ok": 0,
            "all_failed": 0,
        }

    async def route(
        self,
        endpoint: str,
        query_local: Callable[..., Awaitable[Optional[dict]]],
        fetch_liangmai: Callable[..., Awaitable[dict]],
        save_to_db: Optional[Callable[..., Awaitable[None]]] = None,
        params: dict = None,
    ) -> dict:
        """
        两层路由调用

        Args:
            endpoint: 业务端点名
            query_local: 本地DB查询函数，返回 None 表示无数据
            fetch_liangmai: 量脉拉取函数
            save_to_db: 数据入库函数 (量脉成功后调用)
            params: 查询参数

        Returns:
            {"ok": bool, "data": Any, "source": "local"|"liangmai"|"none", "msg": str}
        """
        self._stats["total"] += 1
        params = params or {}

        # ── 第一层：本地 PostgreSQL ──
        try:
            local_result = await query_local(params)
            if local_result is not None:
                self._stats["local_hit"] += 1
                return {"ok": True, "data": local_result, "source": "local", "msg": "ok"}
        except Exception as e:
            log.warning(f"[路由] {endpoint} 本地查询异常: {e}")

        # ── 第二层：量脉 (检查熔断) ──
        if not self._circuit.is_tripped:
            try:
                lm_result = await fetch_liangmai(params)
                if lm_result.get("ok"):
                    self._circuit.record_success()
                    self._stats["liangmai_ok"] += 1
                    data = lm_result.get("data")
                    # 入库
                    if save_to_db and data:
                        try:
                            await save_to_db(params, data, source="liangmai")
                        except Exception as e:
                            log.error(f"[路由] {endpoint} 量脉数据入库失败: {e}")
                    return {"ok": True, "data": data, "source": "liangmai", "msg": "ok"}
                else:
                    msg = lm_result.get("msg", "")
                    self._circuit.record_failure(msg)
                    log.warning(f"[路由] 量脉 {endpoint} 失败: {msg}")
            except Exception as e:
                self._circuit.record_failure(str(e))
                log.error(f"[路由] 量脉 {endpoint} 异常: {e}")
        else:
            log.info(f"[路由] 量脉已熔断，跳过 {endpoint}")

        # ── 两层全失败 ──
        self._stats["all_failed"] += 1
        return {
            "ok": False,
            "data": None,
            "source": "none",
            "msg": f"数据源暂不可用({endpoint})，请稍后重试",
        }

    async def route_simple(
        self,
        endpoint: str,
        liangmai_api: str,
        liangmai_params: dict = None,
        db_table: str = None,
        db_date_field: str = "trade_date",
        trade_date: str = None,
    ) -> dict:
        """
        简化路由：自动处理本地查询 + 量脉

        适用于标准的"按日期查表 → 拉接口 → 入库"模式
        """
        trade_date = trade_date or date.today().isoformat()
        liangmai_params = liangmai_params or {}

        async def query_local(p):
            if not db_table:
                return None
            async with engine.begin() as conn:
                result = await conn.execute(
                    text(f"SELECT * FROM {db_table} WHERE {db_date_field} = :d LIMIT 1"),
                    {"d": trade_date}
                )
                row = result.first()
                if row:
                    result = await conn.execute(
                        text(f"SELECT * FROM {db_table} WHERE {db_date_field} = :d"),
                        {"d": trade_date}
                    )
                    return [dict(r._mapping) for r in result]
                return None

        async def fetch_lm(p):
            return await liangmai.call(liangmai_api, params=liangmai_params, ttl=0)

        return await self.route(
            endpoint=endpoint,
            query_local=query_local,
            fetch_liangmai=fetch_lm,
        )

    def get_stats(self) -> dict:
        return {
            **self._stats,
            "circuit_breaker": self._circuit.get_status(),
        }


router = DataSourceRouter()
