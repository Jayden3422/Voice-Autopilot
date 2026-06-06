from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes

        process_query_limited_information = 0x1000
        still_active = 259
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
        if not handle:
            if kernel32.GetLastError() == 5:
                raise PermissionError(pid)
            return False
        try:
            exit_code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return True
            return exit_code.value == still_active
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


class ProcessStatePublisher:
    def __init__(self, state_dir: str | Path, *, process_type: str) -> None:
        self.state_dir = Path(state_dir)
        self.process_type = process_type
        self.pid = os.getpid()
        self.start_id = uuid.uuid4().hex
        self.started_at = _utc_now().isoformat()
        self.path = self.state_dir / f"{process_type}-{self.pid}-{self.start_id}.json"

    def publish(self, state: dict[str, Any]) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": 1,
            "pid": self.pid,
            "process_type": self.process_type,
            "start_id": self.start_id,
            "started_at": self.started_at,
            "updated_at": _utc_now().isoformat(),
            **state,
        }
        temp = self.path.with_suffix(f".{uuid.uuid4().hex}.tmp")
        try:
            temp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            os.replace(temp, self.path)
        finally:
            temp.unlink(missing_ok=True)

    def remove(self) -> None:
        self.path.unlink(missing_ok=True)


class ProcessStateAggregator:
    def __init__(
        self,
        state_dir: str | Path,
        *,
        ttl_seconds: float,
        pid_alive: Callable[[int], bool] = _pid_alive,
    ) -> None:
        self.state_dir = Path(state_dir)
        self.ttl_seconds = ttl_seconds
        self.pid_alive = pid_alive

    def _remove(self, path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass

    def snapshot(self) -> dict[str, Any]:
        now = _utc_now()
        processes: list[dict[str, Any]] = []
        if not self.state_dir.exists():
            return {"summary": {"process_count": 0, "states": {}}, "processes": []}
        for path in self.state_dir.glob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                required = {
                    "schema_version",
                    "pid",
                    "process_type",
                    "start_id",
                    "started_at",
                    "updated_at",
                    "warmup_state",
                    "resources",
                    "metrics",
                }
                if not required.issubset(payload):
                    raise ValueError("invalid state schema")
                updated_at = datetime.fromisoformat(payload["updated_at"])
                if updated_at.tzinfo is None:
                    updated_at = updated_at.replace(tzinfo=timezone.utc)
                if (now - updated_at).total_seconds() > self.ttl_seconds:
                    raise ValueError("stale")
                try:
                    alive = self.pid_alive(int(payload["pid"]))
                except PermissionError:
                    alive = True
                if not alive:
                    raise ValueError("dead")
                processes.append(payload)
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                self._remove(path)
        states: dict[str, int] = {}
        for process in processes:
            state = str(process["warmup_state"])
            states[state] = states.get(state, 0) + 1
        return {
            "summary": {"process_count": len(processes), "states": states},
            "processes": sorted(processes, key=lambda item: (item["process_type"], item["pid"])),
        }
