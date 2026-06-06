"""
Warmup pool — concurrent startup pre-initialization for expensive resources.

Usage
-----
    pool.register(WarmupTask(provider=my_provider, required=True, retries=2))
    await pool.run_all()

The pool drives all ResourceProvider state transitions.
"""

import asyncio
import logging
import time
from contextlib import suppress
from dataclasses import dataclass

from resources.base import ResourceProvider, ResourceStatus, _TERMINAL_STATUSES

logger = logging.getLogger(__name__)


@dataclass
class WarmupTask:
    provider:    ResourceProvider
    required:    bool  = False
    retries:     int   = 0
    retry_delay: float = 1.0
    timeout:     float = 60.0


class WarmupPool:
    """
    Run WarmupTasks concurrently at startup.

    Concurrency-safe: concurrent run_all() callers share one underlying task via
    asyncio.shield(), so a cancelled caller does not cancel the shared execution.
    """

    def __init__(self, max_concurrent: int = 2) -> None:
        self._tasks:    list[WarmupTask]    = []
        self._max_concurrent                = max_concurrent
        self._lock:     asyncio.Lock        = asyncio.Lock()
        self._run_task: asyncio.Task | None = None

    def register(self, task: WarmupTask) -> None:
        self._tasks.append(task)

    async def run_all(self) -> None:
        async with self._lock:
            if self._run_task is None:
                self._run_task = asyncio.create_task(self._execute_all())
        await asyncio.shield(self._run_task)

    async def _execute_all(self) -> None:
        if not self._tasks:
            return

        sem = asyncio.Semaphore(self._max_concurrent)
        t0  = time.monotonic()

        async def _run_one(wtask: WarmupTask) -> None:
            total  = wtask.retries + 1
            error: str | None = None
            t_task = time.monotonic()

            async with sem:
                for attempt in range(1, total + 1):
                    logger.info(
                        "[warmup] %-20s INITIALIZING  attempt=%d/%d",
                        wtask.provider.name, attempt, total,
                    )
                    try:
                        instance = await asyncio.wait_for(
                            wtask.provider.initialize(),
                            timeout=wtask.timeout,
                        )
                        wtask.provider.mark_ready(instance)
                        logger.info(
                            "[warmup] %-20s READY         elapsed=%.0fms",
                            wtask.provider.name,
                            (time.monotonic() - t_task) * 1000,
                        )
                        return
                    except Exception as exc:
                        error = str(exc)
                        logger.warning(
                            "[warmup] %-20s FAILED        attempt=%d/%d  error=%r",
                            wtask.provider.name, attempt, total, error,
                        )
                        if attempt < total:
                            await asyncio.sleep(wtask.retry_delay)

                wtask.provider.mark_failed(error or "unknown error")

        await asyncio.gather(*[_run_one(t) for t in self._tasks])

        wall_ms  = (time.monotonic() - t0) * 1000
        statuses = [t.provider._status for t in self._tasks]
        logger.info(
            "[warmup] complete  wall=%.0fms  ok=%d skipped=%d failed=%d cancelled=%d",
            wall_ms,
            sum(1 for s in statuses if s is ResourceStatus.READY),
            sum(1 for s in statuses if s is ResourceStatus.SKIPPED),
            sum(1 for s in statuses if s is ResourceStatus.FAILED),
            sum(1 for s in statuses if s is ResourceStatus.CANCELLED),
        )

    async def shutdown(self) -> None:
        """Cancel in-progress warmup; mark non-terminal providers CANCELLED."""
        if self._run_task and not self._run_task.done():
            self._run_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._run_task
        for wtask in self._tasks:
            if wtask.provider._status not in _TERMINAL_STATUSES:
                wtask.provider.mark_cancelled()

    @property
    def state(self) -> str:
        if self._run_task is None:
            return "pending"
        if not self._run_task.done():
            return "running"
        return "complete"

    @property
    def is_done(self) -> bool:
        return self._run_task is not None and self._run_task.done()
