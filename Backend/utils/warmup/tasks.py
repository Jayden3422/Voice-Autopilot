"""
Per-component warmup task functions.

Each function is an async callable that:
  - Returns None on success
  - Raises _SkipWarmup to mark as skipped (resource not ready / optional)
  - Raises any other exception to mark as failed
"""

import asyncio
import logging

from .pool import _SkipWarmup

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Whisper STT
# ---------------------------------------------------------------------------

async def warmup_whisper() -> None:
    """
    Prime the Whisper model with a short silent audio inference.
    The model is already loaded at import time (module-level WhisperModel),
    but the first real inference is slow due to CTranslate2 JIT compilation.
    Running one dummy inference here means the first real STT call is fast.
    """
    import numpy as np
    from tools.speech import (
        _model,
        STT_BEAM_SIZE,
        STT_BEST_OF,
        STT_VAD_FILTER,
        STT_NO_SPEECH_THRESHOLD,
    )

    # 1 second of silence at 16 kHz — minimal cost, primes the compiled kernels
    silence = np.zeros(16_000, dtype=np.float32)
    await asyncio.to_thread(
        lambda: list(
            _model.transcribe(
                silence,
                language="zh",
                beam_size=STT_BEAM_SIZE,
                best_of=STT_BEST_OF,
                vad_filter=STT_VAD_FILTER,
                no_speech_threshold=STT_NO_SPEECH_THRESHOLD,
            )[0]
        )
    )


# ---------------------------------------------------------------------------
# Piper TTS
# ---------------------------------------------------------------------------

async def warmup_piper_zh() -> None:
    """
    Load the Chinese Piper TTS model (xiao_ya) and run a short synthesis.

    This triggers:
      - ONNX model loading via onnxruntime
      - g2pW BERT tokenizer + model loading (the expensive part)
      - First CTranslate2 kernel compilation for the ONNX session

    After warmup the per-call latency drops to ~100–300 ms.
    """
    from tools.speech import _synthesize_speech_sync
    await asyncio.to_thread(_synthesize_speech_sync, "你好", "zh")


async def warmup_piper_en() -> None:
    """
    Load the English Piper TTS model (amy) and run a short synthesis.

    Lighter than the Chinese warmup — no g2pW, espeak-ng phonemisation only.
    """
    from tools.speech import _synthesize_speech_sync
    await asyncio.to_thread(_synthesize_speech_sync, "Hello", "en")


# ---------------------------------------------------------------------------
# OpenAI API connection pool
# ---------------------------------------------------------------------------

async def warmup_openai() -> None:
    """
    Pre-initialize both shared AsyncOpenAI singletons and establish the
    underlying HTTPS connection pool to api.openai.com.

    Why this matters
    ----------------
    httpx (used internally by openai-python) creates its connection pool lazily.
    The first real API call pays for:
      - DNS resolution
      - TLS handshake (~100–300 ms)
      - HTTP/2 session setup
    Making a lightweight `models.list()` call here amortises that cost so that
    the first user-facing extraction / calendar / reply-draft call is instant.

    Both singletons (autopilot_extractor and calendar_extractor) share the same
    api.openai.com base URL, so warming up one pre-populates the OS-level
    connection; we still initialise both objects to avoid any lazy-import cost.
    """
    import os

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key or api_key.startswith("sk-your"):
        raise _SkipWarmup("OPENAI_API_KEY not configured")

    # Initialise both lazy singletons so subsequent callers get a ready client
    from chat.autopilot_extractor import get_openai_client as _get_autopilot_client
    from chat.calendar_extractor import get_openai_client as _get_calendar_client

    autopilot_client = _get_autopilot_client()
    _get_calendar_client()  # initialise the calendar singleton in-place

    # models.list() is the lightest authenticated call: no token cost, fast
    await autopilot_client.models.list()


# ---------------------------------------------------------------------------
# FAISS RAG index
# ---------------------------------------------------------------------------

async def warmup_faiss() -> None:
    """
    Load the FAISS knowledge-base index into memory.

    retrieve.py loads the index lazily on the first query call.  Pre-loading
    here avoids the disk-read latency on the first real autopilot request.
    Skipped if the index hasn't been built yet (run /ingest first).
    """
    from pathlib import Path

    try:
        import faiss
    except ImportError as e:
        raise _SkipWarmup(f"faiss not installed: {e}") from e

    import json
    from rag import retrieve as _retrieve_mod

    index_path = _retrieve_mod.STORE_DIR / "kb.index"
    meta_path = _retrieve_mod.STORE_DIR / "kb_meta.json"

    if not index_path.exists() or not meta_path.exists():
        raise _SkipWarmup("FAISS index not found — run POST /ingest first")

    def _load() -> None:
        index = faiss.read_index(str(index_path))
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        mtime = index_path.stat().st_mtime
        # Populate the module-level cache so the first real query is instant
        _retrieve_mod._faiss_index = index
        _retrieve_mod._faiss_meta = meta
        _retrieve_mod._faiss_index_mtime = mtime
        _retrieve_mod._faiss_meta_mtime = meta_path.stat().st_mtime
        logger.info("[warmup] faiss loaded %d vectors", index.ntotal)

    await asyncio.to_thread(_load)
