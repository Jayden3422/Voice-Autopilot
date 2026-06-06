from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from resources.registry import ResourceRegistry
from utils.warmup.runtime import WarmupRuntime

router = APIRouter(tags=["health"])


def get_runtime(request: Request) -> WarmupRuntime:
    return request.app.state.warmup_runtime


def get_registry(runtime: Annotated[WarmupRuntime, Depends(get_runtime)]) -> ResourceRegistry:
    return runtime.registry


@router.get("/health")
async def health(runtime: Annotated[WarmupRuntime, Depends(get_runtime)]):
    return {"status": "ok", "warmup": runtime.state}


@router.get("/ready")
async def ready(reg: Annotated[ResourceRegistry, Depends(get_registry)]):
    snapshot  = reg.status_snapshot()
    all_ready = reg.all_required_ready()
    content   = {"ready": all_ready, "resources": snapshot}
    status    = 200 if all_ready else 503
    return JSONResponse(status_code=status, content=content)


@router.post("/warmup/retry")
async def retry_warmup(
    runtime: Annotated[WarmupRuntime, Depends(get_runtime)],
    reg: Annotated[ResourceRegistry, Depends(get_registry)],
):
    accepted = await runtime.retry_failed()
    content = {
        "accepted": accepted,
        "warmup": runtime.state,
        "resources": reg.status_snapshot(),
    }
    return JSONResponse(status_code=202 if accepted else 200, content=content)


@router.get("/warmup/status")
async def warmup_status(runtime: Annotated[WarmupRuntime, Depends(get_runtime)]):
    return runtime.status_snapshot()


@router.get("/warmup/cluster")
async def warmup_cluster(runtime: Annotated[WarmupRuntime, Depends(get_runtime)]):
    return runtime.cluster_snapshot()


@router.get("/metrics")
async def metrics(runtime: Annotated[WarmupRuntime, Depends(get_runtime)]):
    content = runtime.metrics_snapshot()
    content["local_process_count"] = runtime.cluster_snapshot()["summary"]["process_count"]
    return content
