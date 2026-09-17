"""全市场快照调度器 — 每 60s 拉取全市场数据写入 PostgreSQL"""
import asyncio, logging, time
from datetime import datetime, date
from typing import Optional
from sqlalchemy import text
from app.liangmai.client import liangmai
from app.database import engine
from app.liangmai.parsing import snapshot_records, source_date
from app.utils import is_trading_day
from zoneinfo import ZoneInfo
from app.services.data_evidence import quote_time

log = logging.getLogger("snapshot.scheduler")

# 交易时间窗口
TRADING_WINDOWS = [
    ("09:15", "11:30"),  # 含集合竞价
    ("13:00", "15:00"),
]

# 快照清理：保留最近 N 个交易日
RETENTION_DAYS = 5


def _in_trading_window() -> bool:
    """检查当前是否在交易时间"""
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    if not is_trading_day(now.date()):  # 周末
        return False
    t = now.strftime("%H:%M")
    return any(start <= t <= end for start, end in TRADING_WINDOWS)


class SnapshotScheduler:
    """全市场快照调度器"""

    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_snapshot_at: Optional[str] = None
        self._snapshot_count = 0
        self._error_count = 0

    async def start(self):
        """启动调度"""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        log.info("快照调度器已启动")

    async def stop(self):
        """停止调度"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        log.info("快照调度器已停止")

    async def _loop(self):
        """主循环：交易时间内每 60s 拉取一次"""
        while self._running:
            try:
                if _in_trading_window():
                    await self._fetch_and_store()
                    await asyncio.sleep(60)
                else:
                    # 非交易时间，每 5 分钟检查一次
                    await asyncio.sleep(300)
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"快照调度异常: {e}")
                self._error_count += 1
                await asyncio.sleep(10)

    async def _fetch_and_store(self):
        """拉取全市场快照并写入数据库"""
        trade_date = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
        snapshot_at = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")

        result = await liangmai.call("market_snapshot_all", ttl=0)
        if not result.get("ok"):
            log.warning(f"快照拉取失败: {result.get('msg')}")
            self._error_count += 1
            return {"ok": False, "msg": result.get("msg"), "code": result.get("code")}

        data = result.get("data")
        if not data:
            log.warning("快照数据为空")
            return {"ok": False, "msg": "上游快照为空，保留已有行情"}

        # data 可能是 list 或 dict
        stocks = [s for s in snapshot_records(data) if source_date(s.get("t")) == trade_date]
        if not stocks:
            log.warning("快照股票列表为空")
            return {"ok": False, "msg": "未找到日期属于今天的有效行情，保留已有数据"}

        # 写入数据库
        await self._batch_insert(trade_date, snapshot_at, stocks)
        self._last_snapshot_at = snapshot_at
        self._snapshot_count += 1
        log.info(f"快照写入完成: {len(stocks)} 只, 第 {self._snapshot_count} 次")
        return {"ok": True, "count": len(stocks), "msg": "快照已入库"}

    async def _batch_insert(self, trade_date: str, snapshot_at: str, stocks: list):
        """批量写入快照数据"""
        if not stocks:
            return

        # 构建批量 INSERT
        rows = []
        for s in stocks:
            code = s.get("code", "")
            if not code:
                continue
            rows.append({
                "trade_date": trade_date,
                "snapshot_at": datetime.fromisoformat(snapshot_at) if isinstance(snapshot_at, str) else snapshot_at,
                "code": code,
                "source_at": quote_time(s.get("t")).replace(tzinfo=None) if quote_time(s.get("t")) else None,
                "name": s.get("mc", s.get("n", s.get("name"))),
                "price": _float(s.get("p", s.get("price"))),
                "pct_chg": _float(s.get("pc", s.get("pct_chg"))),
                "amount": _int(s.get("cje", s.get("amount"))),
                "volume": _int(s.get("v", s.get("volume"))),
                "open": _float(s.get("o", s.get("open"))),
                "high": _float(s.get("h", s.get("high"))),
                "low": _float(s.get("l", s.get("low"))),
                "pre_close": _float(s.get("yc", s.get("pre_close"))),
                "turnover": _float(s.get("hs", s.get("turnover"))),
                "volume_ratio": _float(s.get("lb", s.get("volume_ratio"))),
                "amplitude": _float(s.get("zf", s.get("amplitude"))),
                "circulating_cap": _int(s.get("lt", s.get("circulating_cap"))),
                "total_cap": _int(s.get("sz", s.get("total_cap"))),
            })

        if not rows:
            return

        # 使用 PostgreSQL COPY 风格的批量插入（通过 executemany）
        async with engine.begin() as conn:
            await conn.execute(
                text("""
                    INSERT INTO market_snapshot
                        (trade_date, snapshot_at, source_at, code, name, price, pct_chg, amount, volume,
                         open, high, low, pre_close, turnover, volume_ratio, amplitude,
                         circulating_cap, total_cap)
                    VALUES
                        (:trade_date, :snapshot_at, :source_at, :code, :name, :price, :pct_chg, :amount, :volume,
                         :open, :high, :low, :pre_close, :turnover, :volume_ratio, :amplitude,
                         :circulating_cap, :total_cap)
                """),
                rows,
            )

    async def cleanup_old(self):
        """清理过期快照数据"""
        async with engine.begin() as conn:
            result = await conn.execute(
                text(f"""DELETE FROM market_snapshot s WHERE trade_date < CURRENT_DATE - INTERVAL '{RETENTION_DAYS} days'
                    AND snapshot_at < (SELECT MAX(m.snapshot_at) FROM market_snapshot m WHERE m.trade_date=s.trade_date)""")
            )
            deleted = result.rowcount
            if deleted > 0:
                log.info(f"清理过期快照: {deleted} 条")

    def get_status(self) -> dict:
        return {
            "running": self._running,
            "in_trading_window": _in_trading_window(),
            "last_snapshot_at": self._last_snapshot_at,
            "snapshot_count": self._snapshot_count,
            "error_count": self._error_count,
        }


def _float(v) -> Optional[float]:
    try:
        return float(v) if v is not None else None
    except (ValueError, TypeError):
        return None


def _int(v) -> Optional[int]:
    try:
        return int(float(v)) if v is not None else None
    except (ValueError, TypeError):
        return None


snapshot_scheduler = SnapshotScheduler()
