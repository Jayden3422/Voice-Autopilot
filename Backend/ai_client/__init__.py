from functools import lru_cache
import os

from openai import AsyncOpenAI


@lru_cache(maxsize=1)
def create_openai_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


async def get_openai_client() -> AsyncOpenAI:
    """FastAPI dependency that waits for the managed OpenAI provider."""
    import resources
    from resources import require

    return await require(resources.openai)
