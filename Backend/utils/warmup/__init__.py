"""
utils.warmup — startup warmup coordinator for Voice-Autopilot.

Public API
----------
run_all()           : coroutine — run all enabled warmup tasks (idempotent)
shutdown()          : coroutine — cancel warmup and mark remaining providers CANCELLED
get_warmup_state()  : str — "pending" | "running" | "complete" | "disabled"
"""

import logging
import resources
from .config import load_config
from .pool   import WarmupPool, WarmupTask

__all__ = ["run_all", "shutdown", "get_warmup_state"]

logger = logging.getLogger(__name__)

_config = load_config()
_pool   = WarmupPool(max_concurrent=_config.max_concurrent)

# Map provider name → enabled flag from config
_ENABLED: dict[str, bool] = {
    "whisper_stt":  _config.whisper_enabled,
    "piper_tts_zh": _config.piper_zh_enabled,
    "piper_tts_en": _config.piper_en_enabled,
    "openai":       _config.openai_enabled,
    "faiss":        _config.faiss_enabled,
}


def _setup() -> None:
    if not _config.enabled:
        for provider in resources.registry.all():
            provider.mark_skipped()
        return

    for provider in resources.registry.all():
        if not _ENABLED.get(provider.name, True):
            provider.mark_skipped()
            logger.info("[warmup] %-20s SKIPPED       (disabled by config)", provider.name)
            continue
        _pool.register(WarmupTask(
            provider    = provider,
            required    = provider.required,
            retries     = _config.retries if provider.required else 0,
            retry_delay = _config.retry_delay,
            timeout     = _config.task_timeout,
        ))


_setup()


async def run_all() -> None:
    await _pool.run_all()


async def shutdown() -> None:
    await _pool.shutdown()


def get_warmup_state() -> str:
    if not _config.enabled:
        return "disabled"
    return _pool.state
