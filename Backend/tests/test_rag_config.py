from pathlib import Path
import os
import subprocess
import sys

import pytest


def test_default_rag_config_is_single_host_backend_store(monkeypatch):
    from rag.config import load_rag_config

    monkeypatch.delenv("RAG_DEPLOYMENT_MODE", raising=False)
    monkeypatch.delenv("RAG_STORE_DIR", raising=False)

    config = load_rag_config()

    assert config.deployment_mode == "single-host"
    assert config.store_dir == Path(__file__).resolve().parents[1] / "rag_store"


def test_load_rag_config_resolves_relative_path_without_creating_it(
    monkeypatch, tmp_path
):
    from rag.config import load_rag_config

    relative = "runtime/custom-rag"
    monkeypatch.setenv("RAG_STORE_DIR", relative)

    config = load_rag_config(repo_root=tmp_path)

    assert config.store_dir == tmp_path / relative
    assert not config.store_dir.exists()


def test_validate_rag_config_accepts_and_creates_local_directory(tmp_path):
    from rag.config import RagConfig, validate_rag_config

    store_dir = tmp_path / "local-store"
    config = RagConfig(deployment_mode="single-host", store_dir=store_dir)

    assert validate_rag_config(config) is config
    assert store_dir.is_dir()


@pytest.mark.parametrize("mode", ["multi-host", "distributed", ""])
def test_validate_rag_config_rejects_non_single_host_mode(monkeypatch, mode):
    from rag.config import load_rag_config, validate_rag_config

    monkeypatch.setenv("RAG_DEPLOYMENT_MODE", mode)

    with pytest.raises(ValueError, match="RAG_DEPLOYMENT_MODE"):
        validate_rag_config(load_rag_config())


@pytest.mark.parametrize(
    "store_dir",
    [
        r"\\server\share\rag",
        "smb://server/share",
        "nfs://server/export",
        "s3://bucket/rag",
        "gs://bucket/rag",
        "azure://container/rag",
    ],
)
def test_validate_rag_config_rejects_clear_remote_paths(monkeypatch, store_dir):
    from rag.config import load_rag_config, validate_rag_config

    monkeypatch.setenv("RAG_STORE_DIR", store_dir)

    with pytest.raises(ValueError, match="RAG_STORE_DIR"):
        validate_rag_config(load_rag_config())


def test_default_faiss_provider_uses_rag_config_store_dir(monkeypatch, tmp_path):
    from resources.faiss import FaissProvider

    store_dir = tmp_path / "configured"
    monkeypatch.setenv("RAG_STORE_DIR", str(store_dir))

    assert FaissProvider()._store_dir == store_dir.resolve()


def test_ingest_and_retrieve_use_configured_store_dir(tmp_path):
    store_dir = tmp_path / "configured"
    env = {
        **os.environ,
        "RAG_STORE_DIR": str(store_dir),
        "RAG_DEPLOYMENT_MODE": "single-host",
    }
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from rag import ingest, retrieve; "
                "print(ingest.STORE_DIR); "
                "print(retrieve.STORE_DIR)"
            ),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.splitlines() == [str(store_dir.resolve())] * 2
    assert not store_dir.exists()


def test_importing_rag_modules_does_not_validate_or_create_store(tmp_path):
    store_dir = tmp_path / "unsupported"
    env = {
        **os.environ,
        "RAG_DEPLOYMENT_MODE": "multi-host",
        "RAG_STORE_DIR": str(store_dir),
    }

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from rag import ingest, retrieve; print('ok')",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "ok"
    assert not store_dir.exists()
