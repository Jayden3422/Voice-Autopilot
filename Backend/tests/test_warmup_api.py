from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.health import router
from resources.base import ResourceProvider
from resources.registry import ResourceRegistry
from utils.warmup.config import WarmupConfig
from utils.warmup.runtime import WarmupRuntime
from utils.warmup.state import ProcessStatePublisher


class FakeProvider(ResourceProvider):
    async def _load(self):
        return object()


def make_app(tmp_path):
    registry = ResourceRegistry()
    registry.register(FakeProvider("required", required=True))
    runtime = WarmupRuntime(
        registry=registry,
        config=WarmupConfig(retries=0),
        process_type="test",
        publisher=ProcessStatePublisher(tmp_path, process_type="test"),
    )
    app = FastAPI()
    app.state.warmup_runtime = runtime
    app.include_router(router)
    return app, runtime


def test_status_cluster_metrics_and_existing_endpoints(tmp_path):
    app, runtime = make_app(tmp_path)
    runtime.registry.all()[0].mark_ready(object())

    with TestClient(app) as client:
        assert client.get("/health").json()["warmup"] == "pending"
        assert client.get("/ready").status_code == 200
        assert client.get("/warmup/status").json()["resources"]["required"]["status"] == "ready"
        assert client.get("/warmup/cluster").json()["summary"]["process_count"] == 1
        metrics = client.get("/metrics").json()
        assert metrics["state"] == "pending"
        assert metrics["local_process_count"] == 1
