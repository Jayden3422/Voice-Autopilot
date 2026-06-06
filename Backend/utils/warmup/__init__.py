"""
utils.warmup — global startup warmup pool for Voice-Autopilot.

Public API
----------
pool        : WarmupPool singleton
run_all()   : coroutine — register all project tasks and run them; call once at startup
"""

import logging

from .pool import WarmupPool, WarmupTask

__all__ = [
    "pool",
    "run_all",
    "WarmupPool",
    "WarmupTask",
]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global singleton
# CPU-bound tasks (Whisper + Piper) should not all run at once;
# max_concurrent=2 lets FAISS + one model inference overlap.
# ---------------------------------------------------------------------------
pool = WarmupPool(max_concurrent=2)


async def run_all() -> None:
    """
    Register all warmup tasks and run them concurrently.
    Safe to call multiple times — idempotent via pool._run_task guard.
    """
    if pool.is_done:
        return

    await pool.run_all()
