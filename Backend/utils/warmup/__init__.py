"""Compatibility facade for the process-local warmup runtime."""

from __future__ import annotations

from .config import load_config
from .runtime import WarmupRuntime, create_runtime

__all__ = [
    "WarmupRuntime",
    "create_runtime",
    "get_default_runtime",
    "start",
    "run_all",
    "retry_failed",
    "shutdown",
    "get_warmup_state",
]

_default_runtime: WarmupRuntime | None = None


def get_default_runtime() -> WarmupRuntime:
    global _default_runtime
    if _default_runtime is None:
        import resources

        _default_runtime = create_runtime(
            resources.registry,
            load_config(),
            process_type="default",
        )
    return _default_runtime


def start():
    return get_default_runtime().start()


async def run_all() -> None:
    await get_default_runtime().run_all()


async def retry_failed() -> bool:
    return await get_default_runtime().retry_failed()


async def shutdown() -> None:
    await get_default_runtime().shutdown()


def get_warmup_state() -> str:
    return get_default_runtime().state
