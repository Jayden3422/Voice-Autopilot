import asyncio

import pytest

from resources.base import ResourceProvider
from resources.registry import ResourceRegistry
from utils.warmup.config import WarmupConfig
from utils.warmup.runtime import WarmupRuntime
from utils.warmup.state import ProcessStatePublisher


class FakeProvider(ResourceProvider):
    def __init__(self):
        super().__init__("fake")
        self.closed = False
        self.load_loop = None
        self.close_loop = None

    async def _load(self):
        self.load_loop = asyncio.get_running_loop()
        return self

    async def close(self):
        self.close_loop = asyncio.get_running_loop()
        self.closed = True


@pytest.mark.asyncio
async def test_mcp_lifecycle_warms_before_serving_and_shuts_down_on_one_loop(tmp_path):
    from utils.warmup.mcp_lifecycle import run_mcp_lifecycle

    provider = FakeProvider()
    registry = ResourceRegistry()
    registry.register(provider)
    publisher = ProcessStatePublisher(tmp_path, process_type="mcp")
    runtime = WarmupRuntime(
        registry=registry,
        config=WarmupConfig(retries=0),
        process_type="mcp",
        publisher=publisher,
    )
    served = []
    lifecycle_loop = asyncio.get_running_loop()

    async def serve():
        served.append((provider.is_ready, asyncio.get_running_loop()))

    await run_mcp_lifecycle(runtime, serve)

    assert served == [(True, lifecycle_loop)]
    assert provider.closed is True
    assert provider.load_loop is lifecycle_loop
    assert provider.close_loop is lifecycle_loop
    assert not publisher.path.exists()


@pytest.mark.asyncio
async def test_mcp_lifecycle_shuts_down_when_serve_raises(tmp_path):
    from utils.warmup.mcp_lifecycle import run_mcp_lifecycle

    provider = FakeProvider()
    registry = ResourceRegistry()
    registry.register(provider)
    runtime = WarmupRuntime(
        registry=registry,
        config=WarmupConfig(retries=0),
        process_type="mcp",
        publisher=ProcessStatePublisher(tmp_path, process_type="mcp"),
    )

    async def serve():
        raise RuntimeError("serve failed")

    with pytest.raises(RuntimeError, match="serve failed"):
        await run_mcp_lifecycle(runtime, serve)

    assert provider.closed is True
