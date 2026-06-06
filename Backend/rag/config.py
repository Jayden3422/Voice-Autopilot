from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_REMOTE_PREFIXES = ("smb://", "nfs://", "s3://", "gs://", "azure://")
_DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class RagConfig:
    deployment_mode: str
    store_dir: Path
    raw_store_dir: str | None = None


def load_rag_config(*, repo_root: str | Path | None = None) -> RagConfig:
    mode = os.getenv("RAG_DEPLOYMENT_MODE", "single-host").strip()
    raw_store_dir = os.getenv("RAG_STORE_DIR", "Backend/rag_store").strip()
    store_dir = Path(raw_store_dir).expanduser()
    if raw_store_dir and not _is_remote(raw_store_dir) and not store_dir.is_absolute():
        store_dir = Path(repo_root or _DEFAULT_REPO_ROOT) / store_dir
    if raw_store_dir and not _is_remote(raw_store_dir):
        store_dir = store_dir.resolve()
    return RagConfig(
        deployment_mode=mode,
        store_dir=store_dir,
        raw_store_dir=raw_store_dir,
    )


def validate_rag_config(config: RagConfig) -> RagConfig:
    if config.deployment_mode != "single-host":
        raise ValueError(
            "RAG_DEPLOYMENT_MODE must be 'single-host', "
            f"got {config.deployment_mode!r}"
        )
    raw_store_dir = (
        config.raw_store_dir
        if config.raw_store_dir is not None
        else str(config.store_dir)
    )
    if not raw_store_dir:
        raise ValueError("RAG_STORE_DIR must not be empty")
    if _is_remote(raw_store_dir):
        raise ValueError(
            "RAG_STORE_DIR must use a local filesystem path, "
            f"got {raw_store_dir!r}"
        )
    config.store_dir.mkdir(parents=True, exist_ok=True)
    if not config.store_dir.is_dir():
        raise ValueError(f"RAG_STORE_DIR is not a directory: {config.store_dir}")
    return config


def _is_remote(value: str) -> bool:
    return value.startswith("\\\\") or value.lower().startswith(_REMOTE_PREFIXES)
