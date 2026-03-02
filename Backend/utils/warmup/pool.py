"""
Warmup pool — concurrent startup pre-initialization for expensive resources.

Usage
-----
Register task functions, then call run_all() once at application startup.
Each task is an async callable that returns None (errors are caught and logged).

    pool.register("my_component", my_async_fn)
    await pool.run_all()

The pool tracks per-component status and elapsed time, and exposes them via
results() and summary().
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)


class WarmupStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class WarmupResult:
    name: str
    status: WarmupStatus = WarmupStatus.PENDING
    elapsed_ms: float = 0.0
    error: str = ""

    def __str__(self) -> str:
        if self.status == WarmupStatus.DONE:
            return f"{self.name}: ok ({self.elapsed_ms:.0f}ms)"
        if self.status == WarmupStatus.FAILED:
            return f"{self.name}: FAILED ({self.elapsed_ms:.0f}ms) — {self.error}"
        if self.status == WarmupStatus.SKIPPED:
            return f"{self.name}: skipped"
        return f"{self.name}: {self.status}"


class WarmupPool:
    """
    Run a set of async warmup tasks concurrently at startup.

    Parameters
    ----------
    max_concurrent : int
        Maximum number of tasks running at the same time.  Keep this low (2–3)
        when tasks compete for CPU (e.g. model inference).
    """

    def __init__(self, max_concurrent: int = 2) -> None:
        self._tasks: list[tuple[str, Callable[[], Awaitable[None]]]] = []
        self._max_concurrent = max_concurrent
        self._results: dict[str, WarmupResult] = {}
        self._completed = asyncio.Event()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(
        self,
        name: str,
        fn: Callable[[], Awaitable[None]],
    ) -> None:
        """Register an async warmup function under a display name."""
        self._tasks.append((name, fn))
        self._results[name] = WarmupResult(name=name)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def run_all(self) -> dict[str, WarmupResult]:
        """
        Run all registered warmup tasks respecting max_concurrent.
        Returns the per-component result dict.
        Always resolves — individual failures are logged but do not raise.
        """
        if not self._tasks:
            self._completed.set()
            return {}

        sem = asyncio.Semaphore(self._max_concurrent)

        async def _run(name: str, fn: Callable[[], Awaitable[None]]) -> WarmupResult:
            result = self._results[name]
            result.status = WarmupStatus.RUNNING
            t0 = time.monotonic()
            async with sem:
                try:
                    logger.info("[warmup] %-30s starting", name)
                    await fn()
                    result.status = WarmupStatus.DONE
                    result.elapsed_ms = (time.monotonic() - t0) * 1000
                    logger.info("[warmup] %-30s done    %6.0f ms", name, result.elapsed_ms)
                except _SkipWarmup as e:
                    result.status = WarmupStatus.SKIPPED
                    result.elapsed_ms = (time.monotonic() - t0) * 1000
                    result.error = str(e)
                    logger.info("[warmup] %-30s skipped — %s", name, e)
                except Exception as e:
                    result.status = WarmupStatus.FAILED
                    result.elapsed_ms = (time.monotonic() - t0) * 1000
                    result.error = str(e)[:300]
                    logger.warning(
                        "[warmup] %-30s FAILED  %6.0f ms — %s",
                        name,
                        result.elapsed_ms,
                        result.error,
                    )
            return result

        coros = [_run(name, fn) for name, fn in self._tasks]
        results = await asyncio.gather(*coros, return_exceptions=False)
        self._results = {r.name: r for r in results}
        self._completed.set()

        n_ok = sum(1 for r in results if r.status == WarmupStatus.DONE)
        n_skip = sum(1 for r in results if r.status == WarmupStatus.SKIPPED)
        n_fail = sum(1 for r in results if r.status == WarmupStatus.FAILED)
        total_ms = sum(r.elapsed_ms for r in results)
        logger.info(
            "[warmup] complete — %d ok, %d skipped, %d failed, total wall %.0f ms",
            n_ok,
            n_skip,
            n_fail,
            total_ms,
        )
        return self._results

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def results(self) -> dict[str, WarmupResult]:
        """Return a shallow copy of the current result dict."""
        return dict(self._results)

    def summary(self) -> str:
        """Return a multi-line human-readable warmup report."""
        lines = ["[warmup] results:"]
        for r in self._results.values():
            lines.append(f"  {r}")
        return "\n".join(lines)

    async def wait(self) -> None:
        """Block until all warmup tasks have completed (or failed)."""
        await self._completed.wait()

    @property
    def is_done(self) -> bool:
        return self._completed.is_set()


class _SkipWarmup(Exception):
    """Raise inside a warmup task to mark it as skipped (not a failure)."""
