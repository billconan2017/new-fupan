"""Async gateway client: versioned contracts, bounded retries and shared requests."""
import asyncio
from collections import OrderedDict, deque
from copy import deepcopy
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import time
import re

import httpx
from app.config import get_settings
from app.liangmai.contracts import prepare, unpack, CATALOG


class LiangmaiClient:
    def __init__(self, config=None):
        self.settings = config or get_settings()
        self.gateway = self.settings.liangmai_gateway.rstrip('/')
        self._http = None
        self._cache = OrderedDict()
        self._inflight = {}
        self._rate_lock = asyncio.Lock()
        self._next_request = 0.0
        self._pause_until = 0.0
        self._snapshots = {}
        self._recent = deque(maxlen=30)
        self._stats = dict(remoteCalls=0, cacheHits=0, coalesced=0, errors=0)

    async def connect(self):
        if self._http is None or self._http.is_closed:
            # Query authentication is required by the new official MCP client.
            # Disable httpx INFO request logs: they otherwise include the token URL.
            import logging
            logging.getLogger('httpx').setLevel(logging.WARNING)
            self._http = httpx.AsyncClient(timeout=self.settings.liangmai_timeout,
                limits=httpx.Limits(max_connections=10), trust_env=False, follow_redirects=False)

    async def close(self):
        tasks = list(self._inflight.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        if self._http:
            await self._http.aclose()
        self._cache.clear()

    def _error(self, api, code, msg, **meta):
        return {'ok': False, 'code': code, 'msg': msg, 'data': None,
                '_meta': {'api': api, 'source': 'liangmai', 'cacheHit': False,
                          'dataMissing': True, **meta}}

    async def call(self, api: str, params: dict = None, ttl: int = 0) -> dict:
        try:
            name, p = prepare(api, params)
        except (ValueError, TypeError) as exc:
            return self._error(api, 'invalid_request', str(exc), remoteCalls=0)
        # Canonical keys let old and new names share one request/cache entry.
        key = json.dumps([name, p], sort_keys=True, separators=(',', ':'))
        now = time.monotonic()
        if ttl > 0 and key in self._cache:
            created, stored_ttl, result = self._cache[key]
            if now - created < min(ttl, stored_ttl):
                self._stats['cacheHits'] += 1
                self._cache.move_to_end(key)
                out = deepcopy(result)
                out['_meta'].update(cacheHit=True, cacheAgeSeconds=round(now-created, 3), remoteCalls=0)
                return out
            del self._cache[key]
        shared = key in self._inflight
        if not shared:
            task = asyncio.create_task(self._bounded(name, p, ttl, key))
            self._inflight[key] = task
        else:
            self._stats['coalesced'] += 1
        out = deepcopy(await asyncio.shield(self._inflight[key]))
        if shared:
            out['_meta'].update(coalesced=True, remoteCalls=0)
        return out

    async def _bounded(self, api, params, ttl, key):
        started = time.monotonic()
        try:
            try:
                result = await asyncio.wait_for(self._execute(api, params), self.settings.liangmai_total_timeout)
            except asyncio.TimeoutError:
                result = self._error(api, 'deadline_exceeded', '数据请求超出总时间预算')
            result['_meta']['elapsedMs'] = round((time.monotonic()-started)*1000)
            self._recent.append({k: result['_meta'].get(k) for k in ('api', 'fetchedAt', 'elapsedMs', 'dataMissing')} | {'ok': result['ok'], 'code': result['code']})
            if result['ok'] and not result['_meta'].get('dataMissing') and ttl > 0:
                now = time.monotonic()
                for old in list(self._cache):
                    created, lifetime, _ = self._cache[old]
                    if now-created >= lifetime:
                        del self._cache[old]
                self._cache[key] = (now, ttl, deepcopy(result))
                while len(self._cache) > self.settings.liangmai_cache_max_entries:
                    self._cache.popitem(last=False)
            if not result['ok']:
                self._stats['errors'] += 1
            return result
        finally:
            self._inflight.pop(key, None)

    async def _execute(self, api, params):
        if api == 'market_quote_multi':
            codes = list(dict.fromkeys(c.strip() for c in str(params['stock_codes']).split(',')))
            if not all(re.fullmatch(r'\d{6}', c) for c in codes):
                return self._error(api, 'invalid_request', '股票代码须为逗号分隔的6位代码', remoteCalls=0)
            return await self._batches(api, codes)
        return await self._request(api, params)

    async def _batches(self, api, codes):
        rows, missing, errors = [], [], []
        remote_calls = 0
        for i in range(0, len(codes), 20):
            batch = codes[i:i+20]
            r = await self._request(api, {'stock_codes': ','.join(batch)})
            remote_calls += r['_meta'].get('remoteCalls', 0)
            data = r.get('data')
            if not r['ok'] or not isinstance(data, list):
                missing.extend(batch)
                errors.append(r['code'] if not r['ok'] else 'invalid_response')
                if str(r['code']) in {'401', '403', '429', '60036', 'token_missing'}:
                    missing.extend(codes[i+20:])
                    break
                continue
            rows.extend(data)
            returned = {str(x.get('dm') or x.get('code') or x.get('c') or '').split('.')[0]
                        for x in data if isinstance(x, dict)}
            missing.extend(c for c in batch if c not in returned)
        return {'ok': not missing and not errors, 'code': 0 if not missing and not errors else 'partial_data',
                'msg': 'ok' if not missing and not errors else '部分股票未返回，请检查缺失列表', 'data': rows,
                '_meta': {'api': api, 'source': 'liangmai', 'cacheHit': False,
                          'fetchedAt': datetime.now(timezone.utc).isoformat(), 'dataMissing': bool(missing or errors),
                          'missingCodes': missing, 'batchErrors': errors, 'remoteCalls': remote_calls}}

    async def _slot(self, api):
        async with self._rate_lock:
            now = time.monotonic()
            if self._pause_until > now:
                return self._pause_until-now
            if self._next_request > now:
                await asyncio.sleep(self._next_request-now)
            now = time.monotonic()
            if self._pause_until > now:
                return self._pause_until-now
            if api in {'market_snapshot_all', 'market_quote_all'}:
                until = self._snapshots.get(api, 0)
                if until > now:
                    return until-now
                self._snapshots[api] = now+self.settings.liangmai_snapshot_cooldown
            rate = min(self.settings.liangmai_safe_rate, self.settings.liangmai_peak_rate)
            self._next_request = now + 60 / max(rate, 1)
        return None

    async def _request(self, api, params):
        token = self.settings.liangmai_token
        if not token:
            return self._error(api, 'token_missing', '未配置 LIANGMAI_TOKEN', remoteCalls=0)
        if self._http is None:
            return self._error(api, 'not_connected', '量脉客户端尚未启动', remoteCalls=0)
        calls = 0
        for attempt in range(self.settings.liangmai_max_attempts):
            remaining = await self._slot(api)
            if remaining is not None:
                return self._error(api, 429, '调用冷却中，请稍后重试', retryAfterSeconds=round(remaining, 1), remoteCalls=calls)
            calls += 1
            self._stats['remoteCalls'] += 1
            try:
                response = await self._http.post(f'{self.gateway}/{api}', params={'token': token, 'api': api, **params})
                code = str(response.status_code)
                if response.status_code == 200:
                    try:
                        ok, code, data, codes = unpack(response.json())
                    except (ValueError, TypeError):
                        ok, code, data, codes = False, 'invalid_response', None, []
                    if ok:
                        return {'ok': True, 'code': 0, 'msg': 'ok', 'data': data,
                                '_meta': {'api': api, 'source': 'liangmai', 'cacheHit': False,
                                          'dataMissing': data is None or data == [] or data == {},
                                          'fetchedAt': datetime.now(timezone.utc).isoformat(),
                                          'upstreamCodes': codes, 'remoteCalls': calls, 'attempt': attempt+1}}
                if code in {'429', '60036'}:
                    pause = _retry_after(response.headers.get('Retry-After'))
                    self._pause_until = max(self._pause_until, time.monotonic()+pause)
                    return self._error(api, code, '量脉限流或IP限制，请检查账户出口IP与额度', retryAfterSeconds=pause, remoteCalls=calls)
                if code not in {'500', '502', '503', '504'}:
                    messages = {'401': '量脉认证失败', '403': '量脉权限或IP校验失败',
                                '404': '接口或数据不存在', '422': '量脉参数校验失败',
                                'invalid_response': '量脉响应结构无效'}
                    return self._error(api, code, messages.get(code, '量脉业务请求失败'), remoteCalls=calls)
            except httpx.RequestError:
                # Never return exception strings: query URLs contain credentials.
                code = 'network_error'
            if attempt+1 < self.settings.liangmai_max_attempts:
                await asyncio.sleep(0.4 * (2**attempt))
        return self._error(api, code, '量脉请求重试后仍失败', remoteCalls=calls)

    def get_status(self):
        return {'protocol': 'POST /api/gateway/{api}', 'catalogDate': CATALOG['retrieved'],
                'catalogEndpoints': len(CATALOG['endpoints']), 'tokenConfigured': bool(self.settings.liangmai_token),
                **self._stats, 'cacheEntries': len(self._cache), 'inflight': len(self._inflight),
                'retryAfterSeconds': max(0, round(self._pause_until-time.monotonic(), 1)),
                'recentCalls': list(self._recent)}


def _retry_after(value):
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        try:
            seconds = (parsedate_to_datetime(value)-datetime.now(timezone.utc)).total_seconds()
        except (TypeError, ValueError, OverflowError):
            seconds = 60.0
    return max(1, min(seconds, 3600))


liangmai = LiangmaiClient()
