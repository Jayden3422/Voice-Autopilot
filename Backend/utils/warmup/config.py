import os
import math
from dataclasses import dataclass
from pathlib import Path


def _bool(name: str, default: bool) -> bool:
    val = os.getenv(name, "").lower().strip()
    if val in ("1", "true", "yes", "on"):
        return True
    if val in ("0", "false", "no", "off"):
        return False
    return default


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc


def _float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number, got {raw!r}") from exc
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite, got {raw!r}")
    return value


def _at_least(name: str, value: int | float, minimum: int | float) -> int | float:
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}, got {value}")
    return value


def _greater_than(name: str, value: float, minimum: float) -> float:
    if value <= minimum:
        raise ValueError(f"{name} must be > {minimum}, got {value}")
    return value


@dataclass(frozen=True)
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
    state_dir:        str   = str(Path(__file__).resolve().parents[2] / ".runtime" / "warmup")
    state_ttl_seconds: float = 300.0
    state_heartbeat_seconds: float = 60.0


def load_config() -> WarmupConfig:
    state_ttl_seconds = _greater_than(
        "WARMUP_STATE_TTL_SECONDS",
        _float("WARMUP_STATE_TTL_SECONDS", 300.0),
        0,
    )
    state_heartbeat_seconds = _greater_than(
        "WARMUP_STATE_HEARTBEAT_SECONDS",
        _float("WARMUP_STATE_HEARTBEAT_SECONDS", 60.0),
        0,
    )
    if state_heartbeat_seconds >= state_ttl_seconds:
        raise ValueError(
            "WARMUP_STATE_HEARTBEAT_SECONDS must be less than "
            f"WARMUP_STATE_TTL_SECONDS, got {state_heartbeat_seconds}"
        )
    return WarmupConfig(
        enabled          = _bool( "WARMUP_ENABLED",          True),
        max_concurrent   = int(_at_least(
            "WARMUP_MAX_CONCURRENT", _int("WARMUP_MAX_CONCURRENT", 2), 1
        )),
        task_timeout     = _greater_than(
            "WARMUP_TASK_TIMEOUT", _float("WARMUP_TASK_TIMEOUT", 60.0), 0
        ),
        retries          = int(_at_least(
            "WARMUP_RETRIES", _int("WARMUP_RETRIES", 2), 0
        )),
        retry_delay      = float(_at_least(
            "WARMUP_RETRY_DELAY", _float("WARMUP_RETRY_DELAY", 1.0), 0
        )),
        whisper_enabled  = _bool( "WARMUP_WHISPER_ENABLED",  True),
        piper_zh_enabled = _bool( "WARMUP_PIPER_ZH_ENABLED", True),
        piper_en_enabled = _bool( "WARMUP_PIPER_EN_ENABLED", True),
        openai_enabled   = _bool( "WARMUP_OPENAI_ENABLED",   True),
        faiss_enabled    = _bool( "WARMUP_FAISS_ENABLED",    True),
        state_dir        = os.getenv(
            "WARMUP_STATE_DIR",
            str(Path(__file__).resolve().parents[2] / ".runtime" / "warmup"),
        ),
        state_ttl_seconds = state_ttl_seconds,
        state_heartbeat_seconds = state_heartbeat_seconds,
    )
