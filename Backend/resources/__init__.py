"""
resources — centralized resource providers for Voice-Autopilot.

Public API
----------
    from resources import whisper, piper_zh, piper_en, faiss, openai
    from resources import registry, require, ResourceFailed

All providers are registered in `registry` at import time.
Use `await require(provider)` at call sites to block until ready.
"""

from .base     import ResourceProvider, ResourceFailed, require
from .registry import registry
from .whisper  import WhisperProvider
from .piper    import PiperProvider
from .faiss    import FaissProvider
from .openai   import OpenAIProvider

whisper  = WhisperProvider()
piper_zh = PiperProvider("zh", required=False)
piper_en = PiperProvider("en", required=False)
faiss    = FaissProvider()
openai   = OpenAIProvider()

for _p in (whisper, piper_zh, piper_en, faiss, openai):
    registry.register(_p)

__all__ = [
    "registry",
    "require",
    "ResourceFailed",
    "whisper",
    "piper_zh",
    "piper_en",
    "faiss",
    "openai",
]
