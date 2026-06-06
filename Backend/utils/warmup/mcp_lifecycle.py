from collections.abc import Awaitable, Callable

from .runtime import WarmupRuntime


async def run_mcp_lifecycle(
    runtime: WarmupRuntime,
    serve: Callable[[], Awaitable[None]],
) -> None:
    await runtime.run_all()
    try:
        await serve()
    finally:
        await runtime.shutdown()
