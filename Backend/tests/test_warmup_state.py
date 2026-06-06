import json
import os
from datetime import datetime, timedelta, timezone

from utils.warmup.state import ProcessStateAggregator, ProcessStatePublisher


def record(pid: int, updated_at: datetime) -> dict:
    return {
        "schema_version": 1,
        "pid": pid,
        "process_type": "test",
        "start_id": "start",
        "started_at": updated_at.isoformat(),
        "updated_at": updated_at.isoformat(),
        "warmup_state": "complete",
        "resources": {},
        "metrics": {},
    }


def test_publisher_writes_and_removes_own_record(tmp_path):
    publisher = ProcessStatePublisher(tmp_path, process_type="test")
    publisher.publish({"warmup_state": "running", "resources": {}, "metrics": {}})

    payload = json.loads(publisher.path.read_text(encoding="utf-8"))
    assert payload["pid"] == os.getpid()
    assert payload["warmup_state"] == "running"
    assert not list(tmp_path.glob("*.tmp"))

    publisher.remove()
    assert not publisher.path.exists()


def test_aggregator_skips_and_cleans_invalid_stale_and_dead_records(tmp_path):
    now = datetime.now(timezone.utc)
    (tmp_path / "broken.json").write_text("{", encoding="utf-8")
    (tmp_path / "stale.json").write_text(
        json.dumps(record(os.getpid(), now - timedelta(hours=1))),
        encoding="utf-8",
    )
    (tmp_path / "dead.json").write_text(
        json.dumps(record(99999999, now)),
        encoding="utf-8",
    )
    live = tmp_path / "live.json"
    live.write_text(json.dumps(record(os.getpid(), now)), encoding="utf-8")

    result = ProcessStateAggregator(tmp_path, ttl_seconds=60).snapshot()

    assert len(result["processes"]) == 1
    assert result["summary"]["process_count"] == 1
    assert live.exists()
    assert not (tmp_path / "broken.json").exists()
    assert not (tmp_path / "stale.json").exists()
    assert not (tmp_path / "dead.json").exists()


def test_aggregator_treats_permission_error_as_alive(tmp_path):
    now = datetime.now(timezone.utc)
    path = tmp_path / "unknown.json"
    path.write_text(json.dumps(record(12345, now)), encoding="utf-8")

    aggregator = ProcessStateAggregator(
        tmp_path,
        ttl_seconds=60,
        pid_alive=lambda pid: (_ for _ in ()).throw(PermissionError()),
    )

    assert aggregator.snapshot()["summary"]["process_count"] == 1
    assert path.exists()


def test_aggregator_cleans_record_missing_identity_fields(tmp_path):
    now = datetime.now(timezone.utc)
    invalid = record(os.getpid(), now)
    invalid.pop("process_type")
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(invalid), encoding="utf-8")

    result = ProcessStateAggregator(tmp_path, ttl_seconds=60).snapshot()

    assert result["summary"]["process_count"] == 0
    assert not path.exists()
