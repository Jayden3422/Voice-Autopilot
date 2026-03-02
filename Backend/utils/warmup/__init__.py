"""
utils.warmup — global startup warmup pool for Voice-Autopilot.

Public API
----------
pool        : WarmupPool singleton — use pool.results() / pool.summary() / pool.wait()
run_all()   : coroutine — register all project tasks and run them; call once at startup
"""

import logging

from .pool import WarmupPool, WarmupResult, WarmupStatus
from . import tasks

__all__ = [
    "pool",
    "run_all",
    "WarmupPool",
    "WarmupResult",
    "WarmupStatus",
]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global singleton
# CPU-bound tasks (Whisper + Piper) should not all run at once;
# max_concurrent=2 lets FAISS + one model inference overlap.
# ---------------------------------------------------------------------------
pool = WarmupPool(max_concurrent=2)


def _register_all() -> None:
    """Register every project component with the global pool."""
    # STT — Whisper (CTranslate2 JIT prime)
    pool.register("whisper_stt", tasks.warmup_whisper)
    # TTS — Piper Chinese  (ONNX + g2pW BERT, ~5–15 s first load)
    pool.register("piper_tts_zh", tasks.warmup_piper_zh)
    # TTS — Piper English  (ONNX only, ~1–3 s)
    pool.register("piper_tts_en", tasks.warmup_piper_en)
    # OpenAI — HTTPS connection pool + singleton init (skipped if key missing)
    pool.register("openai_api", tasks.warmup_openai)
    # RAG  — FAISS index   (disk read, skipped if not built)
    pool.register("rag_faiss", tasks.warmup_faiss)


async def run_all() -> None:
    """
    Register all warmup tasks and run them concurrently.
    Safe to call multiple times — tasks are only registered once.
    Logs a full summary when all tasks finish.
    """
    if pool.is_done:
        return

    _register_all()
    await pool.run_all()
    logger.info(pool.summary())
