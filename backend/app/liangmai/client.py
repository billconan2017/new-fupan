"""量脉客户端 v2 — 整合 TokenManager + CooldownManager + Monitor"""
import asyncio, logging, time
from typing import Any, Optional
import httpx
from app.config import get_settings
from app.liangmai.token_manager import TokenManager, CooldownManager, Monitor

log = logging.getLogger("liangmai")
settings = get_settings()

_SNAPSHOT_APIS = frozenset({"market_realtime_all_network"})


class LiangmaiClient:
    """量脉异步客户端"""

    def __init__(self):
        self.gateway = settings.liangmai_gateway
        self._token_mgr = TokenManager([settings.liangmai_token] if settings.liangmai_token else [])
        self._cooldown = CooldownManager(settings.liangmai_snapshot_cooldown)
        self._monitor = Monitor()
        self._http: Optional[httpx.AsyncClient] = None
        self._cache: dict[str, tuple[Any, float]] = {}
        self._cache_ts: dict[str, float] = {}

    async def connect(self):
        self._http = httpx.AsyncClient(
            timeout=httpx.Timeout(20.0),
            limits=httpx.Limits(max_connections=10),
            trust_env=False,
        )
        log.info("量脉客户端已连接")

    async def close(self):
        if self._http:
            await self._http.aclose()

    async def call(self, api: str, params: dict = None, ttl: int = 0) -> dict:
        """
        调用量脉 API

        Returns:
            {"ok": bool, "code": int, "msg": str, "data": Any, "_meta": dict}
        """
        params = params or {}
        cache_key = f"{api}:{params}" if params else api

        # 缓存命中
        if ttl > 0:
            cached = self._cache.get(cache_key)
            if cached and time.time() - self._cache_ts.get(cache_key, 0) < ttl:
                return {**cached, "_meta": {"cacheHit": True}}

        # 快照类接口冷却检查
        if api in _SNAPSHOT_APIS:
            remaining = await self._cooldown.check_snapshot_cooldown()
            if remaining is not None:
                return {"ok": False, "code": -1, "msg": f"快照限流还需{remaining:.0f}s", "data": None}

        # 获取 token
        token = self._token_mgr.get()
        if not token:
            return {"ok": False, "code": -1, "msg": "无可用 token", "data": None}

        # 重试调用
        last_error = None
        for attempt in range(3):
            try:
                data = {"token": token, "api": api}
                if params:
                    data.update(params)

                resp = await self._http.post(self.gateway, data=data)
                status = resp.status_code

                if status == 429:
                    self._token_mgr.mark_limited(token)
                    self._cooldown.record_429()
                    self._monitor.record(api, token, 429, False)
                    # 切换 token 重试
                    token = self._token_mgr.get()
                    if not token:
                        return {"ok": False, "code": 429, "msg": "所有 token 被限速", "data": None}
                    await asyncio.sleep(2 ** attempt)
                    continue

                if status >= 500:
                    self._monitor.record(api, token, status, False)
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue

                resp.raise_for_status()
                result = resp.json()

                self._cooldown.record_success()
                self._monitor.record(api, token, status, True)
                self._token_mgr.release(token)

                ok = result.get("code") in (0, 200)
                if ttl > 0 and ok:
                    self._cache[cache_key] = result
                    self._cache_ts[cache_key] = time.time()

                return {
                    "ok": ok,
                    "code": result.get("code", 0),
                    "msg": result.get("msg", ""),
                    "data": result.get("data"),
                    "_meta": {"api": api, "attempt": attempt + 1, "cacheHit": False},
                }

            except Exception as e:
                last_error = e
                log.warning(f"量脉 {api} attempt {attempt+1}: {e}")
                self._monitor.record(api, token, 0, False)
                if attempt < 2:
                    await asyncio.sleep(0.5 * (attempt + 1))

        return {"ok": False, "code": -1, "msg": f"重试3次失败: {last_error}", "data": None}

    def get_status(self) -> dict:
        """获取客户端状态（供 /health/liangmai 使用）"""
        return {
            "token": self._token_mgr.get_stats(),
            "cooldown": self._cooldown.get_status(),
            "monitor": self._monitor.get_stats(),
        }


liangmai = LiangmaiClient()
