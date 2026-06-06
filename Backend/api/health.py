from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

import utils.warmup as _warmup
from resources.registry import registry as _global_registry, ResourceRegistry

router = APIRouter(tags=["health"])


def get_registry() -> ResourceRegistry:
    return _global_registry


@router.get("/health")
async def health():
    return {"status": "ok", "warmup": _warmup.get_warmup_state()}


@router.get("/ready")
async def ready(reg: Annotated[ResourceRegistry, Depends(get_registry)]):
    snapshot  = reg.status_snapshot()
    all_ready = reg.all_required_ready()
    content   = {"ready": all_ready, "resources": snapshot}
    status    = 200 if all_ready else 503
    return JSONResponse(status_code=status, content=content)
