"""Token 管理器 — 从 8899 迁移，适配 async"""
import time, logging, hashlib, secrets
from typing import Optional

log = logging.getLogger("liangmai.token")

TOKEN_COOLDOWN = 300  # 被限速后冷却 5 分钟


class TokenManager:
    """Token 轮换 + 冷却 + 统计"""

    def __init__(self, tokens: list[str]):
        self._all = list(tokens)
        self._available = list(tokens)
        self._cooldowns: dict[str, float] = {}  # token -> cooldown_until
        self._blacklist: set[str] = set()
        self._use_counts: dict[str, int] = {t: 0 for t in tokens}
        self._last_used: dict[str, float] = {t: 0 for t in tokens}
        self._current = tokens[0] if tokens else None
        self._use_limit_per_token = 20

    def mark_limited(self, token: str):
        """标记 token 被限速"""
        if token in self._blacklist:
            return
        cd_until = time.monotonic() + TOKEN_COOLDOWN
        self._cooldowns[token] = cd_until
        log.warning(f"[token] {token[:8]}... 被限速, 冷却 5 分钟")
        if token in self._available:
            self._available.remove(token)
        self._use_counts[token] = 0

    def mark_blacklisted(self, token: str):
        """标记 token 失效"""
        self._blacklist.add(token)
        if token in self._available:
            self._available.remove(token)
        if token in self._all:
            self._all.remove(token)
        log.error(f"[token] {token[:8]}... 已失效, 拉黑")
        if self._current == token:
            self._current = self._available[0] if self._available else None

    def get(self) -> Optional[str]:
        """获取可用 token（轮换）"""
        now = time.monotonic()
        # 恢复冷却到期的 token
        restored = []
        for t, until in list(self._cooldowns.items()):
            if now >= until:
                del self._cooldowns[t]
                if t not in self._blacklist and t not in self._available:
                    self._available.append(t)
                    self._use_counts[t] = 0
                    restored.append(t)
        if restored:
            log.info(f"[token] 恢复: {[r[:8]+'...' for r in restored]}")

        if not self._available:
            return None

        # 轮换：当前 token 达到使用上限则切换
        if (self._current and self._current in self._available
                and self._use_counts.get(self._current, 0) < self._use_limit_per_token):
            token = self._current
        else:
            # 选使用次数最少的
            token = min(self._available, key=lambda t: self._use_counts.get(t, 0))
            self._current = token

        self._use_counts[token] = self._use_counts.get(token, 0) + 1
        self._last_used[token] = now
        return token

    def release(self, token: str):
        """释放 token（调用完成后）"""
        pass  # 统计用，无需特殊处理

    def get_stats(self) -> dict:
        now = time.monotonic()
        return {
            "total": len(self._all),
            "available": len(self._available),
            "blacklisted": len(self._blacklist),
            "cooling": len(self._cooldowns),
            "current": self._current[:8] + "..." if self._current else None,
            "tokens": [
                {
                    "id": t[:8] + "...",
                    "uses": self._use_counts.get(t, 0),
                    "cooldown_left": max(0, int(self._cooldowns.get(t, 0) - now)),
                    "blacklisted": t in self._blacklist,
                }
                for t in self._all + list(self._blacklist)
            ],
        }

    @property
    def has_available(self) -> bool:
        return len(self._available) > 0


class CooldownManager:
    """快照冷却 + 连续 429 检测"""

    def __init__(self, snapshot_cooldown: int = 60):
        self.snapshot_cooldown = snapshot_cooldown
        self._last_snapshot: float = 0
        self._consecutive_429: int = 0
        self._global_pause_until: float = 0

    async def check_snapshot_cooldown(self) -> Optional[float]:
        now = time.monotonic()
        if now < self._global_pause_until:
            return self._global_pause_until - now
        elapsed = now - self._last_snapshot
        if elapsed < self.snapshot_cooldown:
            return self.snapshot_cooldown - elapsed
        self._last_snapshot = now
        return None

    def record_429(self):
        self._consecutive_429 += 1
        if self._consecutive_429 >= 3:
            pause = min(300, 60 * self._consecutive_429)
            self._global_pause_until = time.monotonic() + pause
            log.warning(f"[cooldown] 连续 {self._consecutive_429} 次 429, 全局暂停 {pause}s")

    def record_success(self):
        self._consecutive_429 = 0

    def get_status(self) -> dict:
        now = time.monotonic()
        return {
            "snapshot_cooldown": self.snapshot_cooldown,
            "consecutive_429": self._consecutive_429,
            "global_pause_remaining": max(0, int(self._global_pause_until - now)),
            "last_snapshot_ago": int(now - self._last_snapshot) if self._last_snapshot else None,
        }


class Monitor:
    """调用监控 + 统计"""

    def __init__(self):
        self._call_log: list[dict] = []
        self._total_calls = 0
        self._total_errors = 0
        self._total_429 = 0
        self._last_429: Optional[float] = None

    def record(self, api: str, token: str, status_code: int, success: bool):
        self._total_calls += 1
        if not success:
            self._total_errors += 1
        if status_code == 429:
            self._total_429 += 1
            self._last_429 = time.time()
        self._call_log.append({
            "time": time.time(),
            "api": api,
            "token": token[:8] + "..." if token else None,
            "status": status_code,
            "success": success,
        })
        if len(self._call_log) > 100:
            self._call_log = self._call_log[-50:]

    def get_stats(self) -> dict:
        return {
            "total_calls": self._total_calls,
            "total_errors": self._total_errors,
            "total_429": self._total_429,
            "last_429": self._last_429,
            "error_rate": round(self._total_errors / max(1, self._total_calls), 4),
            "recent_calls": self._call_log[-10:],
        }
