import os
from dataclasses import dataclass


def _bool(name: str, default: bool) -> bool:
    val = os.getenv(name, "").lower().strip()
    if val in ("1", "true", "yes", "on"):
        return True
    if val in ("0", "false", "no", "off"):
        return False
    return default


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, ""))
    except (ValueError, TypeError):
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, ""))
    except (ValueError, TypeError):
        return default


@dataclass
class WarmupConfig:
    enabled:          bool  = True
    max_concurrent:   int   = 2
    task_timeout:     float = 60.0
    retries:          int   = 2
    retry_delay:      float = 1.0
    whisper_enabled:  bool  = True
    piper_zh_enabled: bool  = True
    piper_en_enabled: bool  = True
    openai_enabled:   bool  = True
    faiss_enabled:    bool  = True


def load_config() -> WarmupConfig:
    return WarmupConfig(
        enabled          = _bool( "WARMUP_ENABLED",          True),
        max_concurrent   = _int(  "WARMUP_MAX_CONCURRENT",   2),
        task_timeout     = _float("WARMUP_TASK_TIMEOUT",     60.0),
        retries          = _int(  "WARMUP_RETRIES",          2),
        retry_delay      = _float("WARMUP_RETRY_DELAY",      1.0),
        whisper_enabled  = _bool( "WARMUP_WHISPER_ENABLED",  True),
        piper_zh_enabled = _bool( "WARMUP_PIPER_ZH_ENABLED", True),
        piper_en_enabled = _bool( "WARMUP_PIPER_EN_ENABLED", True),
        openai_enabled   = _bool( "WARMUP_OPENAI_ENABLED",   True),
        faiss_enabled    = _bool( "WARMUP_FAISS_ENABLED",    True),
    )
