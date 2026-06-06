import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


def load_mcp_server():
    path = Path(__file__).resolve().parents[1] / "mcp" / "mcp_server.py"
    spec = importlib.util.spec_from_file_location("voice_autopilot_mcp_server", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_mcp_entrypoint_resolves_backend_directory():
    mcp_server = load_mcp_server()

    assert mcp_server.BACKEND_DIR == Path(__file__).resolve().parents[1]


@pytest.mark.asyncio
async def test_http_lifespan_rejects_invalid_rag_config_before_runtime(
    monkeypatch,
):
    import main

    monkeypatch.setenv("RAG_DEPLOYMENT_MODE", "multi-host")
    monkeypatch.setattr(
        main,
        "create_runtime",
        lambda *args, **kwargs: pytest.fail("runtime must not be created"),
    )

    with pytest.raises(ValueError, match="RAG_DEPLOYMENT_MODE"):
        async with main._lifespan(SimpleNamespace(state=SimpleNamespace())):
            pass


def test_mcp_entrypoint_rejects_invalid_rag_config_before_runtime(monkeypatch):
    import utils.warmup.runtime

    mcp_server = load_mcp_server()

    monkeypatch.setenv("RAG_DEPLOYMENT_MODE", "multi-host")
    monkeypatch.setattr(
        utils.warmup.runtime,
        "create_runtime",
        lambda *args, **kwargs: pytest.fail("runtime must not be created"),
    )

    with pytest.raises(ValueError, match="RAG_DEPLOYMENT_MODE"):
        mcp_server._run()
