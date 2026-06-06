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
from typing import Any, Callable

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

    def __init__(
        self,
        max_concurrent: int = 2,
        observer: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self._tasks:    list[WarmupTask]    = []
        self._max_concurrent                = max_concurrent
        self._lock:     asyncio.Lock        = asyncio.Lock()
        self._run_task: asyncio.Task | None = None
        self._observer = observer

    def _emit(self, event: str, **data: Any) -> None:
        if self._observer is not None:
            self._observer(event, data)

    def register(self, task: WarmupTask) -> None:
        if self._run_task is not None:
            raise ValueError("warmup pool has already started")
        if any(existing.provider.name == task.provider.name for existing in self._tasks):
            raise ValueError(f"warmup provider '{task.provider.name}' is already registered")
        self._tasks.append(task)

    def start(self) -> asyncio.Task:
        """Start warmup immediately and return the shared execution task."""
        if self._run_task is None:
            self._run_task = asyncio.create_task(self._execute_all())
        return self._run_task

    async def run_all(self) -> None:
        async with self._lock:
            run_task = self.start()
        await asyncio.shield(run_task)

    async def retry_failed(self) -> bool:
        """Start one shared retry execution containing only failed providers."""
        async with self._lock:
            if self._run_task is not None and not self._run_task.done():
                return False
            failed = [
                task for task in self._tasks
                if task.provider._status is ResourceStatus.FAILED
            ]
            if not failed:
                return False
            for task in failed:
                task.provider.reset()
            self._run_task = asyncio.create_task(self._execute_all(failed, retry=True))
            return True

    async def _execute_all(
        self,
        tasks: list[WarmupTask] | None = None,
        *,
        retry: bool = False,
    ) -> None:
        tasks = self._tasks if tasks is None else tasks
        self._emit("execution_started", retry=retry)
        if not tasks:
            self._emit("execution_completed", elapsed_ms=0.0, state=self.state)
            return

        sem = asyncio.Semaphore(self._max_concurrent)
        t0  = time.monotonic()

        async def _run_one(wtask: WarmupTask) -> None:
            total  = wtask.retries + 1
            error: str | None = None
            t_task = time.monotonic()

            async with sem:
                for attempt in range(1, total + 1):
                    self._emit(
                        "attempt_started",
                        resource=wtask.provider.name,
                        attempt=attempt,
                    )
                    logger.info(
                        "event=warmup_resource_initializing resource=%s attempt=%d total_attempts=%d",
                        wtask.provider.name, attempt, total,
                    )
                    try:
                        instance = await asyncio.wait_for(
                            wtask.provider.initialize(),
                            timeout=wtask.timeout,
                        )
                        wtask.provider.mark_ready(instance)
                        self._emit(
                            "resource_ready",
                            resource=wtask.provider.name,
                            elapsed_ms=(time.monotonic() - t_task) * 1000,
                        )
                        logger.info(
                            "event=warmup_resource_ready resource=%s elapsed_ms=%.0f",
                            wtask.provider.name,
                            (time.monotonic() - t_task) * 1000,
                        )
                        return
                    except Exception as exc:
                        error = (
                            f"timed out after {wtask.timeout}s"
                            if isinstance(exc, asyncio.TimeoutError)
                            else str(exc) or type(exc).__name__
                        )
                        logger.warning(
                            "event=warmup_resource_attempt_failed resource=%s attempt=%d total_attempts=%d error=%r",
                            wtask.provider.name, attempt, total, error,
                        )
                        if attempt < total:
                            await asyncio.sleep(wtask.retry_delay)

                wtask.provider.mark_failed(error or "unknown error")
                self._emit(
                    "resource_failed",
                    resource=wtask.provider.name,
                    elapsed_ms=(time.monotonic() - t_task) * 1000,
                )

        await asyncio.gather(*[_run_one(t) for t in tasks])

        wall_ms  = (time.monotonic() - t0) * 1000
        statuses = [t.provider._status for t in tasks]
        logger.info(
            "event=warmup_execution_complete elapsed_ms=%.0f ready=%d skipped=%d failed=%d cancelled=%d",
            wall_ms,
            sum(1 for s in statuses if s is ResourceStatus.READY),
            sum(1 for s in statuses if s is ResourceStatus.SKIPPED),
            sum(1 for s in statuses if s is ResourceStatus.FAILED),
            sum(1 for s in statuses if s is ResourceStatus.CANCELLED),
        )
        self._emit("execution_completed", elapsed_ms=wall_ms, state=self.state)

    async def shutdown(self) -> None:
        """Cancel in-progress warmup; mark non-terminal providers CANCELLED."""
        if self._run_task and not self._run_task.done():
            self._run_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._run_task
        for wtask in self._tasks:
            if wtask.provider._status not in _TERMINAL_STATUSES:
                wtask.provider.mark_cancelled()
        for wtask in self._tasks:
            try:
                await wtask.provider.close()
            except Exception:
                logger.exception(
                    "event=warmup_resource_close_failed resource=%s",
                    wtask.provider.name,
                )

    @property
    def state(self) -> str:
        if self._run_task is None:
            return "pending"
        if not self._run_task.done():
            return "running"
        if self._run_task.cancelled():
            return "cancelled"
        if self._run_task.exception() is not None:
            return "failed"
        if any(t.provider._status is ResourceStatus.FAILED for t in self._tasks):
            return "failed"
        return "complete"

    @property
    def is_done(self) -> bool:
        return self._run_task is not None and self._run_task.done()
