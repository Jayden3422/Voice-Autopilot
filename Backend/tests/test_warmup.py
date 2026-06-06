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
