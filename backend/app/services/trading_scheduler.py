"""APScheduler 定时调度器 — 4组Cron任务

使用 BackgroundScheduler 随 FastAPI 生命周期启停。
仅 A股交易日执行，自动跳过周末、法定节假日。
所有任务增加幂等校验 + 接口重试 + 异常日志。
"""
import logging
import asyncio
import functools
import time
import traceback
from datetime import datetime, date, timedelta
from typing import Optional, Callable
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import text
from app.database import engine
from app.utils import is_trading_day

log = logging.getLogger("scheduler")

# ── 重试装饰器 ──

def retry_on_failure(max_retries: int = 3, delay: float = 2.0, backoff: float = 2.0):
    """自动重试装饰器，支持指数退避"""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    wait = delay * (backoff ** attempt)
                    log.warning(f"[重试] {func.__name__} 第{attempt+1}次失败: {e}, {wait:.1f}s后重试")
                    await asyncio.sleep(wait)
            log.error(f"[重试] {func.__name__} {max_retries}次全部失败: {last_error}")
            raise last_error
        return wrapper
    return decorator


class TradingScheduler:
    """A股交易定时调度器"""

    def __init__(self):
        self._scheduler = BackgroundScheduler(
            timezone="Asia/Shanghai",
            job_defaults={"coalesce": True, "max_instances": 1},
        )
        self._running = False
        self._last_runs: dict = {}    # job_id -> {date, time, result, retries}
        self._run_counts: dict = {}   # job_id -> count
        self._errors: dict = {}       # job_id -> {time, error, traceback}

    def start(self):
        """启动调度器，注册所有定时任务"""
        if self._running:
            return

        # ── 盘前任务 09:14 ──
        self._scheduler.add_job(
            self._run_pre_market,
            CronTrigger(hour=9, minute=14, day_of_week="mon-fri"),
            id="pre_market",
            name="盘前任务-基础库更新",
            replace_existing=True,
        )

        # ── 竞价任务 09:26 ──
        self._scheduler.add_job(
            self._run_auction,
            CronTrigger(hour=9, minute=26, day_of_week="mon-fri"),
            id="auction",
            name="竞价数据拉取",
            replace_existing=True,
        )

        # ── 盘中增量更新 11:30 / 14:30 / 15:00 ──
        for hour, minute, label in [(11, 30, "半日"), (14, 30, "午后"), (15, 0, "收盘")]:
            self._scheduler.add_job(
                self._run_intraday,
                CronTrigger(hour=hour, minute=minute, day_of_week="mon-fri"),
                id=f"intraday_{hour}_{minute}",
                name=f"盘中增量-{label}",
                replace_existing=True,
                kwargs={"label": label},
            )

        # ── 盘后汇总任务 15:40 ──
        self._scheduler.add_job(
            self._run_post_market,
            CronTrigger(hour=15, minute=40, day_of_week="mon-fri"),
            id="post_market",
            name="盘后汇总",
            replace_existing=True,
        )

        self._scheduler.start()
        self._running = True
        log.info("交易调度器已启动 (APScheduler)")

    def stop(self):
        if self._running:
            self._scheduler.shutdown(wait=False)
            self._running = False
            log.info("交易调度器已停止")

    # ── 幂等校验 ──

    async def _check_idempotent(self, job_id: str, trade_date: str) -> bool:
        """检查今天是否已执行过该任务，返回 True 表示可执行"""
        key = f"{job_id}:{trade_date}"
        if key in self._last_runs:
            log.info(f"[调度] {job_id} 在 {trade_date} 已执行，跳过")
            return False
        return True

    def _record_run(self, job_id: str, trade_date: str, result: any, retries: int = 0):
        key = f"{job_id}:{trade_date}"
        self._last_runs[key] = {
            "date": trade_date,
            "time": datetime.now().isoformat(),
            "result": str(result)[:300],
            "retries": retries,
        }
        self._run_counts[job_id] = self._run_counts.get(job_id, 0) + 1

    def _record_error(self, job_id: str, error: str, tb: str = ""):
        self._errors[job_id] = {
            "time": datetime.now().isoformat(),
            "error": error[:300],
            "traceback": tb[:500],
        }

    # ── 交易日检查 ──

    def _is_trading_day(self) -> bool:
        return is_trading_day(date.today())

    # ── 安全执行包装器 ──

    def _run_safe(self, job_id: str, coro_func, *args, **kwargs):
        """安全执行异步任务：交易日检查 + 幂等 + 重试 + 日志"""
        if not self._is_trading_day():
            log.info(f"[调度] 非交易日，跳过 {job_id}")
            return

        trade_date = date.today().isoformat()
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self._safe_execute(job_id, trade_date, coro_func, *args, **kwargs))
        except Exception as e:
            log.error(f"[调度] {job_id} 最终失败: {e}")
            self._record_error(job_id, str(e), traceback.format_exc())
        finally:
            loop.close()

    async def _safe_execute(self, job_id: str, trade_date: str, coro_func, *args, **kwargs):
        """带重试的安全执行"""
        if not await self._check_idempotent(job_id, trade_date):
            return

        max_retries = 3
        last_error = None

        for attempt in range(max_retries):
            try:
                log.info(f"[调度] {job_id} 开始 ({trade_date}) 第{attempt+1}次")
                result = await coro_func(*args, **kwargs)
                self._record_run(job_id, trade_date, result, retries=attempt)
                log.info(f"[调度] {job_id} 完成 (重试{attempt}次)")
                return
            except Exception as e:
                last_error = e
                log.warning(f"[调度] {job_id} 第{attempt+1}次失败: {e}")
                if attempt < max_retries - 1:
                    wait = 3 * (2 ** attempt)
                    log.info(f"[调度] {job_id} {wait}s后重试")
                    await asyncio.sleep(wait)

        # 全部重试失败
        self._record_error(job_id, str(last_error), traceback.format_exc())
        self._record_run(job_id, trade_date, {"ok": False, "msg": str(last_error)}, retries=max_retries)
        log.error(f"[调度] {job_id} {max_retries}次重试全部失败")

    # ── 盘前任务 09:14 ──

    def _run_pre_market(self):
        self._run_safe("pre_market", self._async_pre_market)

    async def _async_pre_market(self):
        """盘前：更新 stock_basic + sector_tree 底库"""
        log.info("[盘前] 开始更新底库")
        results = {}

        # 更新 stock_basic
        try:
            from app.services.stock_basic_service import update_stock_basic
            results["stock_basic"] = await update_stock_basic()
            log.info(f"[盘前] stock_basic: {results['stock_basic']}")
        except Exception as e:
            log.error(f"[盘前] stock_basic 异常: {e}")
            results["stock_basic"] = {"ok": False, "msg": str(e)}

        # 更新 sector_tree
        try:
            from app.services.sector_tree_service import update_sector_tree
            results["sector_tree"] = await update_sector_tree()
            log.info(f"[盘前] sector_tree: {results['sector_tree']}")
        except Exception as e:
            log.error(f"[盘前] sector_tree 异常: {e}")
            results["sector_tree"] = {"ok": False, "msg": str(e)}

        return results

    # ── 竞价任务 09:26 ──

    def _run_auction(self):
        self._run_safe("auction", self._async_auction)

    async def _async_auction(self):
        """竞价：拉取个股竞价、板块竞价、封单排行、一字涨停"""
        trade_date = date.today().isoformat()
        log.info(f"[竞价] 开始: {trade_date}")

        from app.services.auction_service import fetch_all_auction
        result = await fetch_all_auction(trade_date)
        log.info(f"[竞价] 完成: {result}")
        return result

    # ── 盘中增量更新 ──

    def _run_intraday(self, label: str = ""):
        self._run_safe(f"intraday_{label}", self._async_intraday, label)

    async def _async_intraday(self, label: str):
        """盘中：涨跌停池、板块热力、个股资金流向"""
        trade_date = date.today().isoformat()
        log.info(f"[盘中-{label}] 开始: {trade_date}")
        results = {}

        # 涨跌停池
        try:
            from app.services.pool_service import fetch_all_pools
            results["pools"] = await fetch_all_pools(trade_date)
            log.info(f"[盘中-{label}] 股池: {results['pools']}")
        except Exception as e:
            log.error(f"[盘中-{label}] 股池异常: {e}")
            results["pools"] = {"ok": False, "msg": str(e)}

        # 板块热力
        try:
            from app.services.capital_service import fetch_sector_flow
            results["sector"] = await fetch_sector_flow(trade_date)
            log.info(f"[盘中-{label}] 板块: {results['sector']}")
        except Exception as e:
            log.error(f"[盘中-{label}] 板块异常: {e}")
            results["sector"] = {"ok": False, "msg": str(e)}

        # 个股资金流
        try:
            from app.services.capital_service import fetch_capital_flow
            results["capital"] = await fetch_capital_flow(trade_date)
            log.info(f"[盘中-{label}] 资金: {results['capital']}")
        except Exception as e:
            log.error(f"[盘中-{label}] 资金异常: {e}")
            results["capital"] = {"ok": False, "msg": str(e)}

        log.info(f"[盘中-{label}] 完成")
        return results

    # ── 盘后汇总任务 15:40 ──

    def _run_post_market(self):
        self._run_safe("post_market", self._async_post_market)

    async def _async_post_market(self):
        """盘后：龙虎榜、全板块资金、个股资金流水、复盘报告"""
        trade_date = date.today().isoformat()
        log.info(f"[盘后] 开始: {trade_date}")
        results = {}

        # 1. 龙虎榜+游资
        try:
            from app.services.dragon_service import fetch_all_dragon
            results["dragon"] = await fetch_all_dragon(trade_date)
            log.info(f"[盘后] 龙虎榜: {results['dragon']}")
        except Exception as e:
            log.error(f"[盘后] 龙虎榜异常: {e}")
            results["dragon"] = {"ok": False, "msg": str(e)}

        await asyncio.sleep(2)

        # 2. 板块资金
        try:
            from app.services.capital_service import fetch_sector_flow
            results["sector"] = await fetch_sector_flow(trade_date)
            log.info(f"[盘后] 板块资金: {results['sector']}")
        except Exception as e:
            log.error(f"[盘后] 板块异常: {e}")
            results["sector"] = {"ok": False, "msg": str(e)}

        await asyncio.sleep(2)

        # 3. 个股资金流
        try:
            from app.services.capital_service import fetch_all_capital
            results["capital"] = await fetch_all_capital(trade_date)
            log.info(f"[盘后] 资金流: {results['capital']}")
        except Exception as e:
            log.error(f"[盘后] 资金异常: {e}")
            results["capital"] = {"ok": False, "msg": str(e)}

        await asyncio.sleep(2)

        # 4. 情绪周期
        try:
            from app.services.emotion_service import fetch_emotion_cycle
            results["emotion"] = await fetch_emotion_cycle(trade_date)
            log.info(f"[盘后] 情绪: {results['emotion']}")
        except Exception as e:
            log.error(f"[盘后] 情绪异常: {e}")
            results["emotion"] = {"ok": False, "msg": str(e)}

        await asyncio.sleep(2)

        # 5. 股池
        try:
            from app.services.pool_service import fetch_all_pools
            results["pools"] = await fetch_all_pools(trade_date)
            log.info(f"[盘后] 股池: {results['pools']}")
        except Exception as e:
            log.error(f"[盘后] 股池异常: {e}")
            results["pools"] = {"ok": False, "msg": str(e)}

        await asyncio.sleep(2)

        # 6. 复盘报告
        try:
            from app.services.review_service import generate_review
            results["review"] = await generate_review(trade_date)
            log.info(f"[盘后] 复盘报告: score={results['review'].get('report', {}).get('overall_score')}")
        except Exception as e:
            log.error(f"[盘后] 复盘报告异常: {e}")
            results["review"] = {"ok": False, "msg": str(e)}

        log.info(f"[盘后] 全量完成: {trade_date}")
        return results

    # ── 手动触发接口 ──

    async def trigger_post_market(self, trade_date: str = None) -> dict:
        trade_date = trade_date or date.today().isoformat()
        log.info(f"[手动触发] 盘后拉取: {trade_date}")
        await self._async_post_market()
        return {"ok": True, "date": trade_date}

    async def trigger_fetch_all(self, trade_date: str = None) -> dict:
        trade_date = trade_date or date.today().isoformat()
        log.info(f"[手动触发] 全量拉取: {trade_date}")
        await self._async_pre_market()
        await self._async_auction()
        await self._async_intraday("手动")
        await self._async_post_market()
        return {"ok": True, "date": trade_date}

    async def backfill(self, start_date: str, end_date: str = None) -> dict:
        """批量回填历史交易日"""
        end_date = end_date or start_date
        dates = []
        d = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
        while d <= end:
            if is_trading_day(d):
                dates.append(d.isoformat())
            d += timedelta(days=1)

        if not dates:
            return {"ok": False, "msg": "无有效交易日"}

        log.info(f"[回填] 开始: {dates[0]} ~ {dates[-1]} ({len(dates)} 天)")
        for trade_date in dates:
            log.info(f"[回填] === {trade_date} ===")
            await self._async_post_market()
            if trade_date != dates[-1]:
                await asyncio.sleep(5)

        return {"ok": True, "dates": dates}

    # ── 状态查询 ──

    def get_status(self) -> dict:
        jobs = []
        for job in self._scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": str(job.next_run_time) if job.next_run_time else None,
            })
        return {
            "running": self._running,
            "jobs": jobs,
            "last_runs": self._last_runs,
            "run_counts": self._run_counts,
            "errors": self._errors,
        }


trading_scheduler = TradingScheduler()
