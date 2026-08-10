"""盘后批量拉取调度器

三阶段自动拉取：
  盘前  09:05  竞价数据 (auction)
  盘中  11:35  半日快照 + 情绪
  盘后  15:05  全量入库: 股池 → 龙虎榜 → 资金流 → 情绪 → 板块 → 复盘报告

支持手动触发历史回填 (backfill)。
"""
import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Optional
from sqlalchemy import text
from app.database import engine
from app.liangmai.client import liangmai

log = logging.getLogger("batch.scheduler")

# ── 时间窗口定义 ──
PRE_MARKET_TIME = "09:05"    # 竞价
MID_SESSION_TIME = "11:35"   # 半日
POST_MARKET_TIME = "15:05"   # 盘后


class BatchFetchScheduler:
    """统一盘后批量拉取调度器"""

    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_run: dict = {}          # phase -> last run info
        self._run_counts: dict = {}        # phase -> count
        self._errors: dict = {}            # phase -> error count
        self._backfill_lock = asyncio.Lock()

    async def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        log.info("批量拉取调度器已启动")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        log.info("批量拉取调度器已停止")

    # ── 主循环 ──

    async def _loop(self):
        """主循环：按时间窗口触发"""
        executed_today: dict[str, str] = {}  # phase -> date when last executed

        while self._running:
            try:
                now = datetime.now()
                today = date.today().isoformat()
                t = now.strftime("%H:%M")
                weekday = now.weekday()

                # 跳过周末
                if weekday >= 5:
                    await asyncio.sleep(600)
                    continue

                # 盘前 09:05 — 竞价
                if t >= PRE_MARKET_TIME and executed_today.get("pre_market") != today:
                    log.info("[调度] 盘前竞价拉取开始")
                    await self._run_pre_market(today)
                    executed_today["pre_market"] = today

                # 半日 11:35
                if t >= MID_SESSION_TIME and executed_today.get("mid_session") != today:
                    log.info("[调度] 半日数据拉取开始")
                    await self._run_mid_session(today)
                    executed_today["mid_session"] = today

                # 盘后 15:05 — 全量入库
                if t >= POST_MARKET_TIME and executed_today.get("post_market") != today:
                    log.info("[调度] 盘后全量拉取开始")
                    await self._run_post_market(today)
                    executed_today["post_market"] = today

                # 每天重置
                if t < PRE_MARKET_TIME:
                    executed_today.clear()

                await asyncio.sleep(30)  # 30s 检查一次

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"调度循环异常: {e}")
                await asyncio.sleep(10)

    # ── 盘前: 竞价数据 ──

    async def _run_pre_market(self, trade_date: str):
        try:
            from app.services.auction_service import fetch_all_auction
            result = await fetch_all_auction(trade_date)
            self._record("pre_market", trade_date, result)
            log.info(f"[盘前] 竞价拉取完成: {result}")
        except Exception as e:
            log.error(f"[盘前] 竞价拉取异常: {e}")
            self._record_error("pre_market", str(e))

    # ── 半日: 情绪 ──

    async def _run_mid_session(self, trade_date: str):
        try:
            from app.services.emotion_service import fetch_emotion_cycle
            result = await fetch_emotion_cycle(trade_date)
            self._record("mid_session", trade_date, result)
            log.info(f"[半日] 情绪拉取完成: {result}")
        except Exception as e:
            log.error(f"[半日] 情绪拉取异常: {e}")
            self._record_error("mid_session", str(e))

    # ── 盘后: 全量入库 ──

    async def _run_post_market(self, trade_date: str):
        """盘后批量拉取全部模块数据"""
        results = {}

        # 1. 股池 (涨跌停/炸板/强势)
        try:
            from app.services.pool_service import fetch_all_pools
            results["pools"] = await fetch_all_pools(trade_date)
            log.info(f"[盘后] 股池: {results['pools']}")
        except Exception as e:
            log.error(f"[盘后] 股池异常: {e}")
            results["pools"] = {"ok": False, "msg": str(e)}

        # 等 2s 避免限速
        await asyncio.sleep(2)

        # 2. 龙虎榜 + 游资
        try:
            from app.services.dragon_service import fetch_all_dragon
            results["dragon"] = await fetch_all_dragon(trade_date)
            log.info(f"[盘后] 龙虎榜: {results['dragon']}")
        except Exception as e:
            log.error(f"[盘后] 龙虎榜异常: {e}")
            results["dragon"] = {"ok": False, "msg": str(e)}

        await asyncio.sleep(2)

        # 3. 情绪周期
        try:
            from app.services.emotion_service import fetch_emotion_cycle
            results["emotion"] = await fetch_emotion_cycle(trade_date)
            log.info(f"[盘后] 情绪: {results['emotion']}")
        except Exception as e:
            log.error(f"[盘后] 情绪异常: {e}")
            results["emotion"] = {"ok": False, "msg": str(e)}

        await asyncio.sleep(2)

        # 4. 资金流向 (依赖股池/龙虎榜数据)
        try:
            from app.services.capital_service import fetch_all_capital
            results["capital"] = await fetch_all_capital(trade_date)
            log.info(f"[盘后] 资金流: {results['capital']}")
        except Exception as e:
            log.error(f"[盘后] 资金流异常: {e}")
            results["capital"] = {"ok": False, "msg": str(e)}

        await asyncio.sleep(2)

        # 5. 板块资金流
        try:
            from app.services.capital_service import fetch_sector_flow
            results["sector"] = await fetch_sector_flow(trade_date)
            log.info(f"[盘后] 板块资金: {results['sector']}")
        except Exception as e:
            log.error(f"[盘后] 板块资金异常: {e}")
            results["sector"] = {"ok": False, "msg": str(e)}

        await asyncio.sleep(2)

        # 6. 复盘报告 (依赖上面全部数据)
        try:
            from app.services.review_service import generate_review
            results["review"] = await generate_review(trade_date)
            log.info(f"[盘后] 复盘报告: score={results['review'].get('report', {}).get('overall_score')}")
        except Exception as e:
            log.error(f"[盘后] 复盘报告异常: {e}")
            results["review"] = {"ok": False, "msg": str(e)}

        self._record("post_market", trade_date, results)
        log.info(f"[盘后] 全量拉取完成: {trade_date}")

    # ── 历史回填 ──

    async def backfill(self, start_date: str, end_date: str = None) -> dict:
        """批量回填历史交易日数据

        Args:
            start_date: 起始日期 YYYY-MM-DD
            end_date: 结束日期 (默认同一天)

        Returns:
            {"ok": True, "dates": [...], "results": {...}}
        """
        async with self._backfill_lock:
            end_date = end_date or start_date

            # 生成日期列表 (跳过周末)
            dates = []
            d = datetime.strptime(start_date, "%Y-%m-%d").date()
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
            while d <= end:
                if d.weekday() < 5:
                    dates.append(d.isoformat())
                d += timedelta(days=1)

            if not dates:
                return {"ok": False, "msg": "无有效交易日"}

            log.info(f"[回填] 开始: {dates[0]} ~ {dates[-1]} ({len(dates)} 天)")
            all_results = {}

            for trade_date in dates:
                log.info(f"[回填] === {trade_date} ===")
                day_result = {}

                # 股池
                try:
                    from app.services.pool_service import fetch_all_pools
                    day_result["pools"] = await fetch_all_pools(trade_date)
                except Exception as e:
                    day_result["pools"] = {"ok": False, "msg": str(e)}

                await asyncio.sleep(3)

                # 龙虎榜
                try:
                    from app.services.dragon_service import fetch_all_dragon
                    day_result["dragon"] = await fetch_all_dragon(trade_date)
                except Exception as e:
                    day_result["dragon"] = {"ok": False, "msg": str(e)}

                await asyncio.sleep(3)

                # 情绪
                try:
                    from app.services.emotion_service import fetch_emotion_cycle
                    day_result["emotion"] = await fetch_emotion_cycle(trade_date)
                except Exception as e:
                    day_result["emotion"] = {"ok": False, "msg": str(e)}

                await asyncio.sleep(3)

                # 资金流
                try:
                    from app.services.capital_service import fetch_all_capital
                    day_result["capital"] = await fetch_all_capital(trade_date)
                except Exception as e:
                    day_result["capital"] = {"ok": False, "msg": str(e)}

                await asyncio.sleep(3)

                # 竞价
                try:
                    from app.services.auction_service import fetch_all_auction
                    day_result["auction"] = await fetch_all_auction(trade_date)
                except Exception as e:
                    day_result["auction"] = {"ok": False, "msg": str(e)}

                await asyncio.sleep(3)

                # 板块资金
                try:
                    from app.services.capital_service import fetch_sector_flow
                    day_result["sector"] = await fetch_sector_flow(trade_date)
                except Exception as e:
                    day_result["sector"] = {"ok": False, "msg": str(e)}

                await asyncio.sleep(3)

                # 复盘报告
                try:
                    from app.services.review_service import generate_review
                    day_result["review"] = await generate_review(trade_date)
                except Exception as e:
                    day_result["review"] = {"ok": False, "msg": str(e)}

                all_results[trade_date] = day_result
                log.info(f"[回填] {trade_date} 完成")

                # 日期间间隔 5s 避免限速
                if trade_date != dates[-1]:
                    await asyncio.sleep(5)

            log.info(f"[回填] 全部完成: {len(dates)} 天")
            return {"ok": True, "dates": dates, "results": all_results}

    # ── 手动触发当日盘后 ──

    async def trigger_post_market(self, trade_date: str = None) -> dict:
        """手动触发盘后拉取"""
        trade_date = trade_date or date.today().isoformat()
        log.info(f"[手动触发] 盘后拉取: {trade_date}")
        await self._run_post_market(trade_date)
        return {"ok": True, "date": trade_date, "msg": "盘后拉取已执行"}

    # ── 状态查询 ──

    def get_status(self) -> dict:
        return {
            "running": self._running,
            "last_run": self._last_run,
            "run_counts": self._run_counts,
            "errors": self._errors,
        }

    # ── 记录 ──

    def _record(self, phase: str, trade_date: str, result):
        self._last_run[phase] = {
            "date": trade_date,
            "time": datetime.now().isoformat(),
            "result_summary": str(result)[:200],
        }
        self._run_counts[phase] = self._run_counts.get(phase, 0) + 1

    def _record_error(self, phase: str, error: str):
        self._errors[phase] = {
            "time": datetime.now().isoformat(),
            "error": error[:200],
        }


batch_scheduler = BatchFetchScheduler()
