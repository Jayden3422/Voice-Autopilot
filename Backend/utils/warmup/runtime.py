from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from pathlib import Path
from typing import Any

from resources.registry import ResourceRegistry

from .config import WarmupConfig
from .metrics import WarmupMetrics
from .pool import WarmupPool, WarmupTask
from .state import ProcessStateAggregator, ProcessStatePublisher

logger = logging.getLogger(__name__)


class WarmupRuntime:
    def __init__(
        self,
        *,
        registry: ResourceRegistry,
        config: WarmupConfig,
        process_type: str,
        publisher: ProcessStatePublisher | None,
    ) -> None:
        self.registry = registry
        self.config = config
        self.process_type = process_type
        self.publisher = publisher
        self.metrics = WarmupMetrics()
        self.pool = WarmupPool(max_concurrent=config.max_concurrent, observer=self._observe)
        self._shutdown = False
        self._heartbeat_task: asyncio.Task | None = None
        self._wire_tasks()
        self.registry.freeze()
        self._publish()

    def _wire_tasks(self) -> None:
        enabled = {
            "whisper_stt": self.config.whisper_enabled,
            "piper_tts_zh": self.config.piper_zh_enabled,
            "piper_tts_en": self.config.piper_en_enabled,
            "openai": self.config.openai_enabled,
            "faiss": self.config.faiss_enabled,
        }
        for provider in self.registry.all():
            if not self.config.enabled or not enabled.get(provider.name, True):
                provider.mark_skipped()
                continue
            self.pool.register(WarmupTask(
                provider=provider,
                required=provider.required,
                retries=self.config.retries if provider.required else 0,
                retry_delay=self.config.retry_delay,
                timeout=self.config.task_timeout,
            ))

    def _observe(self, event: str, data: dict[str, Any]) -> None:
        self.metrics.observe(event, data)
        self._publish()

    def _publish(self) -> None:
        if self.publisher is None:
            return
        try:
            self.publisher.publish(self.status_snapshot())
        except OSError:
            logger.warning("event=warmup_state_publish_failed", exc_info=True)

    @property
    def state(self) -> str:
        if not self.config.enabled:
            return "disabled"
        return self.pool.state

    def status_snapshot(self) -> dict[str, Any]:
        metric_resources = self.metrics.snapshot()["resources"]
        resources = {}
        for provider in self.registry.all():
            details = metric_resources.get(provider.name, {})
            resources[provider.name] = {
                "status": provider._status.value,
                "required": provider.required,
                "attempts": details.get("attempts", 0),
                "elapsed_ms": details.get("elapsed_ms", 0.0),
                "error": provider._error[:300] or None,
            }
        return {
            "warmup_state": self.state,
            "resources": resources,
            "metrics": self.metrics_snapshot(),
        }

    def metrics_snapshot(self) -> dict[str, Any]:
        snapshot = self.metrics.snapshot()
        counts: dict[str, int] = {}
        for provider in self.registry.all():
            status = provider._status.value
            counts[status] = counts.get(status, 0) + 1
            details = snapshot["resources"].setdefault(provider.name, {"attempts": 0})
            details["status"] = status
        snapshot["state"] = self.state
        snapshot["resource_counts"] = counts
        return snapshot

    def cluster_snapshot(self) -> dict[str, Any]:
        if self.publisher is None:
            return {"summary": {"process_count": 0, "states": {}}, "processes": []}
        return ProcessStateAggregator(
            self.publisher.state_dir,
            ttl_seconds=self.config.state_ttl_seconds,
        ).snapshot()

    def _ensure_heartbeat(self) -> None:
        if self.publisher is None or self._shutdown:
            return
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def _heartbeat_loop(self) -> None:
        while True:
            await asyncio.sleep(self.config.state_heartbeat_seconds)
            self._publish()

    def start(self):
        self._ensure_heartbeat()
        task = self.pool.start()
        task.add_done_callback(lambda _: self._publish())
        self._publish()
        return task

    async def run_all(self) -> None:
        self._ensure_heartbeat()
        await self.pool.run_all()
        self._publish()

    async def retry_failed(self) -> bool:
        self._ensure_heartbeat()
        accepted = await self.pool.retry_failed()
        self._publish()
        return accepted

    async def shutdown(self) -> None:
        if self._shutdown:
            return
        self._shutdown = True
        if self._heartbeat_task is not None and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._heartbeat_task
        await self.pool.shutdown()
        self._publish()
        if self.publisher is not None:
            try:
                self.publisher.remove()
            except OSError:
                logger.warning("event=warmup_state_remove_failed", exc_info=True)


def create_runtime(
    registry: ResourceRegistry,
    config: WarmupConfig,
    *,
    process_type: str,
    state_dir: str | Path | None = None,
) -> WarmupRuntime:
    publisher = ProcessStatePublisher(
        state_dir or config.state_dir,
        process_type=process_type,
    )
    return WarmupRuntime(
        registry=registry,
        config=config,
        process_type=process_type,
        publisher=publisher,
    )
