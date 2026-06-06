import asyncio
import os

from .base import ResourceProvider


class WhisperProvider(ResourceProvider):
    def __init__(self) -> None:
        super().__init__("whisper_stt", required=True)

    async def _load(self):
        import numpy as np
        from faster_whisper import WhisperModel

        model_name   = os.getenv("WHISPER_MODEL",              "small")
        device       = os.getenv("WHISPER_DEVICE",             "cpu")
        compute_type = os.getenv("WHISPER_COMPUTE_TYPE",       "int8")
        beam_size    = int(os.getenv("WHISPER_BEAM_SIZE",      "1"))
        best_of      = int(os.getenv("WHISPER_BEST_OF",        "1"))
        vad_filter   = os.getenv("WHISPER_VAD_FILTER", "true").lower() not in {"0","false","no"}
        no_speech_th = float(os.getenv("WHISPER_NO_SPEECH_THRESHOLD", "0.5"))

        model = await asyncio.to_thread(
            WhisperModel, model_name, device=device, compute_type=compute_type
        )

        # Prime CTranslate2 JIT kernels with 1s silence
        silence = np.zeros(16_000, dtype=np.float32)
        await asyncio.to_thread(
            lambda: list(
                model.transcribe(
                    silence,
                    language="zh",
                    beam_size=beam_size,
                    best_of=best_of,
                    vad_filter=vad_filter,
                    no_speech_threshold=no_speech_th,
                )[0]
            )
        )
        return model
