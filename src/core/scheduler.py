"""
调度引擎 — 定时扫描并执行到期的策略实例

每 10 秒扫描一次 strategy_instances 表，
找出 status=running 且 next_check_time <= now 的实例，
并发执行（限制并发数避免 API 限速）。
"""

import asyncio
import logging
from datetime import datetime

from core.models import get_runnable_instances, update_strategy_instance, now_iso
from core.executor import execute_strategy_tick

logger = logging.getLogger(__name__)

SCAN_INTERVAL = 10  # 扫描间隔 (秒)
MAX_CONCURRENT = 5  # 最大并发策略执行数


class Scheduler:
    """异步调度引擎"""

    def __init__(self, exchange=None):
        self.exchange = exchange
        self._running = False
        self._task: asyncio.Task | None = None
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    async def start(self):
        """启动调度循环"""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("Scheduler started")

    async def stop(self):
        """停止调度"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Scheduler stopped")

    async def _loop(self):
        """主循环"""
        while self._running:
            try:
                await self._scan_and_execute()
            except Exception as e:
                logger.error(f"Scheduler scan error: {e}", exc_info=True)
            await asyncio.sleep(SCAN_INTERVAL)

    async def _scan_and_execute(self):
        """扫描到期实例并并发执行"""
        now = now_iso()
        instances = get_runnable_instances(now)

        if not instances:
            return

        logger.info(f"Scheduler: {len(instances)} instances ready to execute")

        tasks = [self._execute_one(inst) for inst in instances]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for inst, res in zip(instances, results):
            if isinstance(res, Exception):
                logger.error(f"Execution error [{inst.id[:8]}]: {res}")
                update_strategy_instance(inst.id, error_message=str(res))

    async def _execute_one(self, inst):
        """在信号量控制下执行单个策略 tick"""
        async with self._semaphore:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                execute_strategy_tick,
                inst,
                self.exchange,
            )
            if result.get("action") not in ("none", "skip"):
                logger.info(
                    f"[{inst.id[:8]}] {inst.strategy_name}/{inst.symbol} "
                    f"→ {result['action']}: {result.get('message', '')}"
                )
            return result

    @property
    def is_running(self) -> bool:
        return self._running
