import os

from .base import ResourceProvider


class OpenAIProvider(ResourceProvider):
    def __init__(self) -> None:
        super().__init__("openai", required=False)

    async def _load(self):
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key or api_key.startswith("sk-your"):
            raise RuntimeError("OPENAI_API_KEY not configured")

        # Calling create_openai_client() triggers the lru_cache, creating the
        # AsyncOpenAI singleton. No network call is made here.
        from ai_client import create_openai_client
        return create_openai_client()
