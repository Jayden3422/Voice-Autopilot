import asyncio
import inspect
from abc import ABC, abstractmethod
from enum import Enum
from typing import Generic, TypeVar

T = TypeVar("T")


class ResourceStatus(str, Enum):
    PENDING      = "pending"
    INITIALIZING = "initializing"
    READY        = "ready"
    FAILED       = "failed"
    SKIPPED      = "skipped"
    CANCELLED    = "cancelled"


_TERMINAL_STATUSES: frozenset["ResourceStatus"] = frozenset({
    ResourceStatus.READY,
    ResourceStatus.FAILED,
    ResourceStatus.SKIPPED,
    ResourceStatus.CANCELLED,
})


class ResourceFailed(Exception):
    """Raised by require() when a resource is not READY."""


class ResourceProvider(ABC, Generic[T]):
    def __init__(self, name: str, required: bool = False) -> None:
        self.name     = name
        self.required = required
        self._instance: T | None = None
        self._status  = ResourceStatus.PENDING
        self._done    = asyncio.Event()
        self._error   = ""
        self._closed  = False

    @abstractmethod
    async def _load(self) -> T: ...

    async def initialize(self) -> T:
        """One attempt. Returns loaded instance. Raises on failure. Does NOT set _done."""
        self._status = ResourceStatus.INITIALIZING
        return await self._load()

    def mark_ready(self, instance: T) -> None:
        if self._done.is_set():
            return
        self._instance = instance
        self._status   = ResourceStatus.READY
        self._done.set()

    def mark_failed(self, error: str) -> None:
        if self._done.is_set():
            return
        self._error  = error
        self._status = ResourceStatus.FAILED
        self._done.set()

    def mark_skipped(self) -> None:
        if self._done.is_set():
            return
        self._status = ResourceStatus.SKIPPED
        self._done.set()

    def mark_cancelled(self) -> None:
        if self._done.is_set():
            return
        self._status = ResourceStatus.CANCELLED
        self._done.set()

    def reset(self) -> None:
        """Reset a failed provider so the warmup pool can retry it."""
        if self._status is not ResourceStatus.FAILED:
            raise RuntimeError(f"Resource '{self.name}' cannot reset from {self._status}")
        self._instance = None
        self._status   = ResourceStatus.PENDING
        self._error    = ""
        self._done.clear()
        self._closed   = False

    def get(self) -> T:
        if self._status is not ResourceStatus.READY:
            raise ResourceFailed(f"'{self.name}' not ready (status={self._status})")
        return self._instance  # type: ignore[return-value]

    async def wait_for(self, timeout: float | None = None) -> None:
        if timeout is None:
            await self._done.wait()
        else:
            await asyncio.wait_for(self._done.wait(), timeout=timeout)

    async def close(self) -> None:
        """Close the loaded resource instance when it exposes a close method."""
        if self._closed or self._instance is None:
            return
        self._closed = True
        close = getattr(self._instance, "close", None) or getattr(self._instance, "aclose", None)
        if close is None:
            return
        result = close()
        if inspect.isawaitable(result):
            await result

    @property
    def is_ready(self) -> bool:
        return self._status is ResourceStatus.READY


async def require(provider: "ResourceProvider[T]") -> T:
    """Await _done, then return instance or raise ResourceFailed."""
    await provider.wait_for()
    if not provider.is_ready:
        raise ResourceFailed(
            f"Resource '{provider.name}' unavailable: "
            f"{provider._error or provider._status}"
        )
    return provider.get()
