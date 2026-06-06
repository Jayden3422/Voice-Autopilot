import asyncio
import json

import pytest

from resources.base import ResourceProvider
from resources.registry import ResourceRegistry
from utils.warmup.config import WarmupConfig
from utils.warmup.runtime import WarmupRuntime
from utils.warmup.state import ProcessStatePublisher


class FakeProvider(ResourceProvider):
    def __init__(self, name: str, *, fail: bool = False):
        super().__init__(name)
        self.fail = fail
        self.closed = False

    async def _load(self):
        if self.fail:
            raise RuntimeError("boom")
        return self

    async def close(self):
        self.closed = True


def make_runtime(*providers: FakeProvider) -> WarmupRuntime:
    registry = ResourceRegistry()
    for provider in providers:
        registry.register(provider)
    return WarmupRuntime(
        registry=registry,
        config=WarmupConfig(retries=0, retry_delay=0),
        process_type="test",
        publisher=None,
    )


@pytest.mark.asyncio
async def test_two_runtimes_are_isolated():
    left = make_runtime(FakeProvider("left"))
    right = make_runtime(FakeProvider("right"))

    await left.run_all()

    assert left.state == "complete"
    assert right.state == "pending"
    assert left.registry.status_snapshot() == {"left": "ready"}
    assert right.registry.status_snapshot() == {"right": "pending"}


@pytest.mark.asyncio
async def test_runtime_metrics_track_success_failure_and_retry():
    good = FakeProvider("good")
    bad = FakeProvider("bad", fail=True)
    runtime = make_runtime(good, bad)

    await runtime.run_all()
    bad.fail = False
    assert await runtime.retry_failed() is True
    await runtime.run_all()

    metrics = runtime.metrics_snapshot()
    assert metrics["execution_count"] == 2
    assert metrics["retry_execution_count"] == 1
    assert metrics["total_elapsed_ms"] >= 0
    assert metrics["resources"]["good"]["attempts"] == 1
    assert metrics["resources"]["bad"]["attempts"] == 2
    assert metrics["resources"]["bad"]["status"] == "ready"


@pytest.mark.asyncio
async def test_runtime_shutdown_is_idempotent_and_closes_resources():
    provider = FakeProvider("closable")
    runtime = make_runtime(provider)
    await runtime.run_all()

    await runtime.shutdown()
    await runtime.shutdown()

    assert provider.closed is True


def test_runtime_freezes_registry():
    runtime = make_runtime(FakeProvider("one"))

    with pytest.raises(ValueError, match="frozen"):
        runtime.registry.register(FakeProvider("two"))


@pytest.mark.asyncio
async def test_compatibility_facade_delegates_to_default_runtime(monkeypatch):
    import utils.warmup as warmup

    runtime = make_runtime(FakeProvider("compat"))
    monkeypatch.setattr(warmup, "_default_runtime", runtime)

    await warmup.run_all()

    assert warmup.get_warmup_state() == "complete"


@pytest.mark.asyncio
async def test_runtime_heartbeat_starts_once_and_refreshes_state(tmp_path):
    registry = ResourceRegistry()
    registry.register(FakeProvider("heartbeat"))
    publisher = ProcessStatePublisher(tmp_path, process_type="test")
    runtime = WarmupRuntime(
        registry=registry,
        config=WarmupConfig(
            retries=0,
            state_ttl_seconds=1,
            state_heartbeat_seconds=0.02,
        ),
        process_type="test",
        publisher=publisher,
    )
    initial = json.loads(publisher.path.read_text(encoding="utf-8"))["updated_at"]

    runtime.start()
    first_task = runtime._heartbeat_task
    await runtime.run_all()
    assert runtime._heartbeat_task is first_task
    await asyncio.sleep(0.04)

    updated = json.loads(publisher.path.read_text(encoding="utf-8"))["updated_at"]
    assert updated > initial

    await runtime.shutdown()
    assert first_task.done()
    assert not publisher.path.exists()
