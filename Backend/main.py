import logging
import os
import socket

from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import uvicorn
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fastapi import Request
from fastapi.responses import JSONResponse

from api.autopilot import router as autopilot_router
from api.health    import router as health_router
from api.settings  import router as settings_router
from api.voice     import router as voice_router
from rag.config import load_rag_config, validate_rag_config
from resources.base import ResourceFailed
import resources
from utils.warmup.config import load_config
from utils.warmup.runtime import create_runtime


@asynccontextmanager
async def _lifespan(app: FastAPI):
    validate_rag_config(load_rag_config())
    runtime = create_runtime(resources.registry, load_config(), process_type="http")
    app.state.warmup_runtime = runtime
    runtime.start()
    yield
    await runtime.shutdown()


app = FastAPI(title="Voice Schedule Assistant", lifespan=_lifespan)
app.include_router(autopilot_router)
app.include_router(health_router)
app.include_router(settings_router)
app.include_router(voice_router)

@app.exception_handler(ResourceFailed)
async def _resource_failed_handler(request: Request, exc: ResourceFailed):
    return JSONResponse(
        status_code=503,
        content={"error": "service_unavailable", "detail": str(exc)},
    )

logger = logging.getLogger(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


if __name__ == "__main__":
    def _int_env(name: str, default: int) -> int:
        raw = os.getenv(name)
        if raw is None:
            return default
        try:
            return int(raw)
        except ValueError:
            return default

    def _is_bindable(host: str, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port))
                return True
            except OSError:
                return False

    def _pick_port(host: str, preferred_port: int, retries: int) -> int:
        if _is_bindable(host, preferred_port):
            return preferred_port

        fallback_base = _int_env("BACKEND_FALLBACK_PORT", 8080)
        fallback_retries = max(0, _int_env("BACKEND_PORT_RETRIES", 200))
        for offset in range(0, fallback_retries + 1):
            candidate = fallback_base + offset
            if candidate == preferred_port:
                continue
            if _is_bindable(host, candidate):
                logger.warning(
                    "Preferred port %s is unavailable; using fallback port %s",
                    preferred_port,
                    candidate,
                )
                return candidate

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, 0))
            except OSError as e:
                raise RuntimeError(
                    f"Failed to find any available port on host {host}. "
                    "Check firewall/antivirus policy or run with a different BACKEND_HOST."
                ) from e
            random_port = int(sock.getsockname()[1])

        logger.warning(
            "No available port in configured ranges; using OS-assigned port %s",
            random_port,
        )
        return random_port

    host = os.getenv("BACKEND_HOST", "127.0.0.1")
    preferred_port = _int_env("BACKEND_PORT", 8888)
    port_retries = max(0, _int_env("BACKEND_PORT_RETRIES", 0))
    reload_enabled = os.getenv("BACKEND_RELOAD", "true").lower() in ("1", "true", "yes", "on")

    selected_port = _pick_port(host, preferred_port, port_retries)
    print(f"Starting backend on {host}:{selected_port} (reload={reload_enabled})")
    logger.info("Starting backend on %s:%s (reload=%s)", host, selected_port, reload_enabled)
    uvicorn.run("main:app", host=host, port=selected_port, reload=reload_enabled)
