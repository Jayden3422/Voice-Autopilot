from __future__ import annotations

from typing import Any


class WarmupMetrics:
    def __init__(self) -> None:
        self.execution_count = 0
        self.retry_execution_count = 0
        self.failure_count = 0
        self.total_elapsed_ms = 0.0
        self.resources: dict[str, dict[str, Any]] = {}

    def observe(self, event: str, data: dict[str, Any]) -> None:
        name = data.get("resource")
        if event == "execution_started":
            self.execution_count += 1
            if data.get("retry"):
                self.retry_execution_count += 1
        elif event == "attempt_started" and name:
            resource = self.resources.setdefault(name, {"attempts": 0})
            resource["attempts"] += 1
            resource["status"] = "initializing"
        elif event in {"resource_ready", "resource_failed"} and name:
            resource = self.resources.setdefault(name, {"attempts": 0})
            resource["status"] = "ready" if event == "resource_ready" else "failed"
            resource["elapsed_ms"] = round(float(data.get("elapsed_ms", 0.0)), 3)
            if event == "resource_failed":
                self.failure_count += 1
        elif event == "execution_completed":
            self.total_elapsed_ms = round(
                self.total_elapsed_ms + float(data.get("elapsed_ms", 0.0)),
                3,
            )

    def snapshot(self) -> dict[str, Any]:
        return {
            "execution_count": self.execution_count,
            "retry_execution_count": self.retry_execution_count,
            "failure_count": self.failure_count,
            "total_elapsed_ms": self.total_elapsed_ms,
            "resources": {name: dict(values) for name, values in self.resources.items()},
        }
