"""
Warmup system test suite — all providers faked, no real models loaded.
Each test uses an isolated ResourceRegistry, never the global singleton.
"""
import asyncio
import pytest

from resources.base import (
    ResourceProvider,
    ResourceStatus,
    ResourceFailed,
    _TERMINAL_STATUSES,
    require,
)
from resources.registry import ResourceRegistry
from utils.warmup.pool import WarmupPool, WarmupTask


# ── Shared fake ────────────────────────────────────────────────────────────────

class FakeProvider(ResourceProvider):
    def __init__(self, name: str, required: bool = False, *,
                 fail: bool = False, delay: float = 0.0, load_fn=None):
        super().__init__(name, required)
        self._fail       = fail
        self._delay      = delay
        self._load_fn    = load_fn
        self.load_calls  = 0

    async def _load(self):
        self.load_calls += 1
        if self._load_fn is not None:
            return await self._load_fn()
        if self._delay > 0:
            await asyncio.sleep(self._delay)
        if self._fail:
            raise RuntimeError("deliberate failure")
        return object()


# ── Base / ResourceProvider ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_mark_ready_sets_instance_status_and_done():
    p = FakeProvider("x")
    obj = object()
    p.mark_ready(obj)
    assert p._status is ResourceStatus.READY
    assert p._done.is_set()
    assert p.get() is obj
    assert p.is_ready


@pytest.mark.asyncio
async def test_mark_failed_sets_status_error_and_done():
    p = FakeProvider("x")
    p.mark_failed("boom")
    assert p._status is ResourceStatus.FAILED
    assert p._error == "boom"
    assert p._done.is_set()
    assert not p.is_ready


@pytest.mark.asyncio
async def test_mark_skipped_sets_status_and_done():
    p = FakeProvider("x")
    p.mark_skipped()
    assert p._status is ResourceStatus.SKIPPED
    assert p._done.is_set()


@pytest.mark.asyncio
async def test_mark_cancelled_sets_status_and_done():
    p = FakeProvider("x")
    p.mark_cancelled()
    assert p._status is ResourceStatus.CANCELLED
    assert p._done.is_set()


def test_get_raises_if_not_ready():
    p = FakeProvider("x")
    with pytest.raises(ResourceFailed):
        p.get()


@pytest.mark.asyncio
async def test_initialize_sets_initializing_and_returns_instance():
    p = FakeProvider("x")
    result = await p.initialize()
    assert p._status is ResourceStatus.INITIALIZING
    assert result is not None
    assert not p._done.is_set()   # _done NOT set by initialize()


@pytest.mark.asyncio
async def test_require_returns_instance_when_ready():
    p = FakeProvider("x")
    obj = object()
    p.mark_ready(obj)
    assert await require(p) is obj


@pytest.mark.asyncio
async def test_require_raises_on_failed():
    p = FakeProvider("x")
    p.mark_failed("oops")
    with pytest.raises(ResourceFailed, match="oops"):
        await require(p)


@pytest.mark.asyncio
async def test_require_raises_on_skipped():
    p = FakeProvider("x")
    p.mark_skipped()
    with pytest.raises(ResourceFailed):
        await require(p)


@pytest.mark.asyncio
async def test_require_raises_on_cancelled():
    p = FakeProvider("x")
    p.mark_cancelled()
    with pytest.raises(ResourceFailed):
        await require(p)


@pytest.mark.asyncio
async def test_terminal_statuses_set():
    assert ResourceStatus.READY     in _TERMINAL_STATUSES
    assert ResourceStatus.FAILED    in _TERMINAL_STATUSES
    assert ResourceStatus.SKIPPED   in _TERMINAL_STATUSES
    assert ResourceStatus.CANCELLED in _TERMINAL_STATUSES
    assert ResourceStatus.PENDING       not in _TERMINAL_STATUSES
    assert ResourceStatus.INITIALIZING  not in _TERMINAL_STATUSES


# ── ResourceRegistry ───────────────────────────────────────────────────────────

def test_registry_register_and_all():
    reg = ResourceRegistry()
    p1 = FakeProvider("a")
    p2 = FakeProvider("b", required=True)
    reg.register(p1)
    reg.register(p2)
    assert set(p.name for p in reg.all()) == {"a", "b"}


def test_registry_rejects_duplicate_name():
    reg = ResourceRegistry()
    reg.register(FakeProvider("a"))

    with pytest.raises(ValueError, match="already registered"):
        reg.register(FakeProvider("a"))


def test_registry_rejects_registration_after_freeze():
    reg = ResourceRegistry()
    reg.freeze()

    with pytest.raises(ValueError, match="frozen"):
        reg.register(FakeProvider("a"))


def test_registry_required_filters_required_only():
    reg = ResourceRegistry()
    reg.register(FakeProvider("opt", required=False))
    req = FakeProvider("req", required=True)
    reg.register(req)
    assert reg.required() == [req]


def test_registry_all_required_ready_true():
    reg = ResourceRegistry()
    p = FakeProvider("r", required=True)
    p.mark_ready(object())
    reg.register(p)
    assert reg.all_required_ready()


def test_registry_all_required_ready_false_when_pending():
    reg = ResourceRegistry()
    reg.register(FakeProvider("r", required=True))
    assert not reg.all_required_ready()


def test_registry_status_snapshot():
    reg = ResourceRegistry()
    p = FakeProvider("x")
    p.mark_skipped()
    reg.register(p)
    snap = reg.status_snapshot()
    assert snap == {"x": "skipped"}


# ── WarmupConfig ───────────────────────────────────────────────────────────────

import os
from utils.warmup.config import WarmupConfig, load_config


def test_config_defaults():
    cfg = load_config()
    assert cfg.enabled is True
    assert cfg.max_concurrent == 2
    assert cfg.task_timeout == 60.0
    assert cfg.retries == 2
    assert cfg.retry_delay == 1.0
    assert cfg.whisper_enabled is True


def test_config_env_override(monkeypatch):
    monkeypatch.setenv("WARMUP_ENABLED", "false")
    monkeypatch.setenv("WARMUP_MAX_CONCURRENT", "4")
    monkeypatch.setenv("WARMUP_RETRIES", "0")
    monkeypatch.setenv("WARMUP_WHISPER_ENABLED", "0")
    cfg = load_config()
    assert cfg.enabled is False
    assert cfg.max_concurrent == 4
    assert cfg.retries == 0
    assert cfg.whisper_enabled is False


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("WARMUP_MAX_CONCURRENT", "0"),
        ("WARMUP_MAX_CONCURRENT", "invalid"),
        ("WARMUP_TASK_TIMEOUT", "0"),
        ("WARMUP_TASK_TIMEOUT", "nan"),
        ("WARMUP_TASK_TIMEOUT", "inf"),
        ("WARMUP_RETRIES", "-1"),
        ("WARMUP_RETRIES", "1.5"),
        ("WARMUP_RETRY_DELAY", "-0.1"),
        ("WARMUP_RETRY_DELAY", "nan"),
        ("WARMUP_STATE_TTL_SECONDS", "0"),
        ("WARMUP_STATE_TTL_SECONDS", "nan"),
        ("WARMUP_STATE_HEARTBEAT_SECONDS", "0"),
        ("WARMUP_STATE_HEARTBEAT_SECONDS", "nan"),
    ],
)
def test_config_rejects_invalid_numeric_values(monkeypatch, name, value):
    monkeypatch.setenv(name, value)

    with pytest.raises(ValueError, match=name):
        load_config()


def test_config_rejects_heartbeat_not_below_ttl(monkeypatch):
    monkeypatch.setenv("WARMUP_STATE_TTL_SECONDS", "10")
    monkeypatch.setenv("WARMUP_STATE_HEARTBEAT_SECONDS", "10")

    with pytest.raises(ValueError, match="WARMUP_STATE_HEARTBEAT_SECONDS"):
        load_config()


# ── WarmupPool helpers ─────────────────────────────────────────────────────────

def make_pool(tasks: list[WarmupTask], max_concurrent: int = 8) -> WarmupPool:
    pool = WarmupPool(max_concurrent=max_concurrent)
    for t in tasks:
        pool.register(t)
    return pool


# ── WarmupPool tests ───────────────────────────────────────────────────────────

def test_register_task():
    p = FakeProvider("a")
    pool = WarmupPool(max_concurrent=2)
    task = WarmupTask(provider=p)
    pool.register(task)
    assert len(pool._tasks) == 1
    assert pool._tasks[0].provider is p


def test_pool_rejects_duplicate_provider_name():
    pool = WarmupPool()
    pool.register(WarmupTask(provider=FakeProvider("a")))

    with pytest.raises(ValueError, match="already registered"):
        pool.register(WarmupTask(provider=FakeProvider("a")))


@pytest.mark.asyncio
async def test_pool_rejects_registration_after_execution_starts():
    pool = WarmupPool()
    pool.start()

    with pytest.raises(ValueError, match="started"):
        pool.register(WarmupTask(provider=FakeProvider("a")))

    await pool.run_all()


@pytest.mark.asyncio
async def test_run_all_success():
    p = FakeProvider("a")
    pool = make_pool([WarmupTask(provider=p)])
    await pool.run_all()
    assert p.is_ready


@pytest.mark.asyncio
async def test_run_all_twice_tasks_run_once():
    p = FakeProvider("a")
    pool = make_pool([WarmupTask(provider=p)])
    await pool.run_all()
    await pool.run_all()
    assert p.load_calls == 1
    assert p.is_ready


@pytest.mark.asyncio
async def test_concurrent_run_all_tasks_run_once():
    p = FakeProvider("a")
    pool = make_pool([WarmupTask(provider=p)])
    await asyncio.gather(pool.run_all(), pool.run_all(), pool.run_all())
    assert p.load_calls == 1
    assert p.is_ready


@pytest.mark.asyncio
async def test_start_immediately_tracks_shared_run_task():
    p = FakeProvider("a", delay=0.05)
    pool = make_pool([WarmupTask(provider=p)])

    first = pool.start()
    second = pool.start()

    assert first is second
    assert pool._run_task is first
    await first
    assert p.load_calls == 1
    assert p.is_ready


@pytest.mark.asyncio
async def test_cancelled_caller_does_not_cancel_pool():
    completed = False

    async def slow():
        nonlocal completed
        await asyncio.sleep(0.15)
        completed = True
        return object()

    p   = FakeProvider("slow", load_fn=slow)
    pool = make_pool([WarmupTask(provider=p)])

    t1 = asyncio.create_task(pool.run_all())
    t2 = asyncio.create_task(pool.run_all())
    await asyncio.sleep(0.02)
    t1.cancel()
    with pytest.raises(asyncio.CancelledError):
        await t1
    await t2
    assert completed
    assert p.is_ready


@pytest.mark.asyncio
async def test_semaphore_limit():
    running = 0
    max_running = 0

    async def counting():
        nonlocal running, max_running
        running += 1
        max_running = max(max_running, running)
        await asyncio.sleep(0.02)
        running -= 1
        return object()

    providers = [FakeProvider(f"p{i}", load_fn=counting) for i in range(6)]
    tasks = [WarmupTask(provider=p) for p in providers]
    pool = make_pool(tasks, max_concurrent=2)
    await pool.run_all()
    assert max_running <= 2
    assert all(p.is_ready for p in providers)


@pytest.mark.asyncio
async def test_optional_task_failure_others_complete():
    bad  = FakeProvider("bad",  fail=True)
    good = FakeProvider("good")
    pool = make_pool([WarmupTask(provider=bad), WarmupTask(provider=good)])
    await pool.run_all()
    assert bad._status  is ResourceStatus.FAILED
    assert good.is_ready


@pytest.mark.asyncio
async def test_required_task_retries_on_failure():
    calls = 0

    async def flaky():
        nonlocal calls
        calls += 1
        if calls < 3:
            raise RuntimeError(f"fail {calls}")
        return object()

    p    = FakeProvider("flaky", required=True, load_fn=flaky)
    pool = make_pool([WarmupTask(provider=p, required=True, retries=2, retry_delay=0.01)])
    await pool.run_all()
    assert calls == 3
    assert p.is_ready


@pytest.mark.asyncio
async def test_required_task_exhausted_marks_failed():
    p    = FakeProvider("bad", required=True, fail=True)
    pool = make_pool([WarmupTask(provider=p, required=True, retries=2, retry_delay=0.01)])
    await pool.run_all()
    assert p._status is ResourceStatus.FAILED
    assert "deliberate failure" in p._error
    assert p._done.is_set()


@pytest.mark.asyncio
async def test_task_timeout_marks_failed():
    p    = FakeProvider("slow", delay=10.0)
    pool = make_pool([WarmupTask(provider=p, timeout=0.05)])
    await pool.run_all()
    assert p._status is ResourceStatus.FAILED
    assert p._error == "timed out after 0.05s"
    assert p._done.is_set()


@pytest.mark.asyncio
async def test_wall_clock_accuracy():
    p    = FakeProvider("slow", delay=0.1)
    pool = make_pool([WarmupTask(provider=p)])
    t0   = asyncio.get_running_loop().time()
    await pool.run_all()
    assert (asyncio.get_running_loop().time() - t0) >= 0.08


@pytest.mark.asyncio
async def test_shutdown_marks_running_provider_cancelled():
    slow = FakeProvider("slow", delay=5.0)
    pool = make_pool([WarmupTask(provider=slow)])

    run = asyncio.create_task(pool.run_all())
    await asyncio.sleep(0.02)
    await pool.shutdown()

    try:
        await run
    except (asyncio.CancelledError, Exception):
        pass

    assert slow._status is ResourceStatus.CANCELLED
    assert slow._done.is_set()


@pytest.mark.asyncio
async def test_shutdown_closes_ready_provider_instance():
    closed = False

    class Closable:
        async def close(self):
            nonlocal closed
            closed = True

    p = FakeProvider("closable", load_fn=lambda: asyncio.sleep(0, result=Closable()))
    pool = make_pool([WarmupTask(provider=p)])

    await pool.run_all()
    await pool.shutdown()

    assert closed


@pytest.mark.asyncio
async def test_pool_state_transitions():
    p    = FakeProvider("a", delay=0.05)
    pool = make_pool([WarmupTask(provider=p)])
    assert pool.state == "pending"
    run = asyncio.create_task(pool.run_all())
    await asyncio.sleep(0.01)
    assert pool.state == "running"
    await run
    assert pool.state == "complete"


@pytest.mark.asyncio
async def test_pool_state_failed_when_provider_failed():
    p = FakeProvider("bad", fail=True)
    pool = make_pool([WarmupTask(provider=p)])

    await pool.run_all()

    assert pool.state == "failed"


@pytest.mark.asyncio
async def test_pool_state_cancelled_after_shutdown():
    p = FakeProvider("slow", delay=5.0)
    pool = make_pool([WarmupTask(provider=p)])
    pool.start()
    await asyncio.sleep(0.01)

    await pool.shutdown()

    assert pool.state == "cancelled"


def test_failed_provider_can_be_reset_for_retry():
    p = FakeProvider("failed")
    p.mark_failed("boom")

    p.reset()

    assert p._status is ResourceStatus.PENDING
    assert p._error == ""
    assert p._instance is None
    assert not p._done.is_set()


@pytest.mark.asyncio
async def test_retry_failed_runs_only_failed_providers():
    failed = FakeProvider("failed", fail=True)
    ready = FakeProvider("ready")
    pool = make_pool([WarmupTask(provider=failed), WarmupTask(provider=ready)])
    await pool.run_all()
    failed._fail = False

    accepted = await pool.retry_failed()
    await pool.run_all()

    assert accepted is True
    assert failed.load_calls == 2
    assert failed.is_ready
    assert ready.load_calls == 1


@pytest.mark.asyncio
async def test_concurrent_retry_failed_starts_one_execution():
    failed = FakeProvider("failed", fail=True)
    pool = make_pool([WarmupTask(provider=failed)])
    await pool.run_all()
    failed._fail = False
    failed._delay = 0.05

    accepted = await asyncio.gather(pool.retry_failed(), pool.retry_failed())
    await pool.run_all()

    assert accepted.count(True) == 1
    assert failed.load_calls == 2
    assert failed.is_ready


@pytest.mark.asyncio
async def test_retry_failed_is_noop_when_nothing_failed():
    ready = FakeProvider("ready")
    pool = make_pool([WarmupTask(provider=ready)])
    await pool.run_all()

    accepted = await pool.retry_failed()

    assert accepted is False
    assert ready.load_calls == 1


# ── Health endpoints ───────────────────────────────────────────────────────────

def _make_test_app(reg: ResourceRegistry):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api.health import router as health_router
    from utils.warmup.runtime import WarmupRuntime

    app = FastAPI()
    app.state.warmup_runtime = WarmupRuntime(
        registry=reg,
        config=WarmupConfig(retries=0),
        process_type="test",
        publisher=None,
    )
    app.include_router(health_router)
    return TestClient(app)


def test_health_endpoint_always_200():
    client = _make_test_app(ResourceRegistry())
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert "warmup" in r.json()


def test_ready_503_when_required_provider_pending():
    reg = ResourceRegistry()
    reg.register(FakeProvider("whisper_stt", required=True))
    client = _make_test_app(reg)
    r = client.get("/ready")
    assert r.status_code == 503
    assert r.json()["ready"] is False
    assert r.json()["resources"]["whisper_stt"] == "pending"


def test_ready_200_when_all_required_ready():
    p = FakeProvider("whisper_stt", required=True)
    p.mark_ready(object())
    reg = ResourceRegistry()
    reg.register(p)
    client = _make_test_app(reg)
    r = client.get("/ready")
    assert r.status_code == 200
    assert r.json()["ready"] is True
    assert r.json()["resources"]["whisper_stt"] == "ready"


def test_ready_503_when_required_provider_failed():
    p = FakeProvider("whisper_stt", required=True)
    p.mark_failed("model not found")
    reg = ResourceRegistry()
    reg.register(p)
    client = _make_test_app(reg)
    r = client.get("/ready")
    assert r.status_code == 503
    assert r.json()["resources"]["whisper_stt"] == "failed"


def test_ready_200_no_required_providers():
    reg = ResourceRegistry()
    client = _make_test_app(reg)
    r = client.get("/ready")
    assert r.status_code == 200
    assert r.json()["ready"] is True


def test_retry_endpoint_returns_202_when_retry_started(monkeypatch):
    reg = ResourceRegistry()
    failed = FakeProvider("faiss")
    failed.mark_failed("missing")
    reg.register(failed)

    async def retry_failed():
        failed.reset()
        return True

    client = _make_test_app(reg)
    runtime = client.app.state.warmup_runtime
    monkeypatch.setattr(runtime, "retry_failed", retry_failed)

    response = client.post("/warmup/retry")

    assert response.status_code == 202
    assert response.json() == {
        "accepted": True,
        "warmup": runtime.state,
        "resources": {"faiss": "pending"},
    }


def test_retry_endpoint_returns_200_when_nothing_failed(monkeypatch):
    reg = ResourceRegistry()
    ready = FakeProvider("whisper_stt", required=True)
    ready.mark_ready(object())
    reg.register(ready)

    async def retry_failed():
        return False

    client = _make_test_app(reg)
    monkeypatch.setattr(client.app.state.warmup_runtime, "retry_failed", retry_failed)

    response = client.post("/warmup/retry")

    assert response.status_code == 200
    assert response.json()["accepted"] is False
    assert response.json()["resources"] == {"whisper_stt": "ready"}
