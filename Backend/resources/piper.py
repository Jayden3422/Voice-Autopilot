import asyncio
import os
from pathlib import Path

from .base import ResourceProvider


class PiperProvider(ResourceProvider):
    def __init__(self, lang: str, required: bool = False) -> None:
        super().__init__(f"piper_tts_{lang}", required)
        self._lang = lang

    async def _load(self):
        from piper import PiperVoice

        models_dir = Path(os.getenv(
            "PIPER_MODELS_DIR",
            str(Path(__file__).resolve().parent.parent / "models" / "piper"),
        ))

        if self._lang == "zh":
            model_path = os.getenv(
                "PIPER_ZH_MODEL",
                str(models_dir / "zh_CN-xiao_ya-medium.onnx"),
            )
            prime_text = "你好"
        else:
            model_path = os.getenv(
                "PIPER_EN_MODEL",
                str(models_dir / "en_US-amy-medium.onnx"),
            )
            prime_text = "Hello"

        voice = await asyncio.to_thread(PiperVoice.load, model_path, False)
        # Prime ONNX session with a short synthesis
        await asyncio.to_thread(lambda: list(voice.synthesize(prime_text)))
        return voice
