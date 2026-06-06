import asyncio
import importlib
import os
import threading
from pathlib import Path

from .base import ResourceProvider


_G2PW_INIT_LOCK = threading.Lock()


def _load_chinese_phonemizer(factory):
    g2pw_api = importlib.import_module("g2pw.api")
    onnxruntime = g2pw_api.onnxruntime
    original_inference_session = onnxruntime.InferenceSession

    def inference_session(*args, sess_options=None, **kwargs):
        if sess_options is not None:
            sess_options.graph_optimization_level = (
                onnxruntime.GraphOptimizationLevel.ORT_DISABLE_ALL
            )
        return original_inference_session(
            *args,
            sess_options=sess_options,
            **kwargs,
        )

    # g2pw hard-codes ORT_ENABLE_ALL, which can hang while optimizing its model.
    with _G2PW_INIT_LOCK:
        onnxruntime.InferenceSession = inference_session
        try:
            return factory()
        finally:
            onnxruntime.InferenceSession = original_inference_session


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

        voice = await asyncio.to_thread(PiperVoice.load, model_path, use_cuda=False)
        if self._lang == "zh":
            from piper.phonemize_chinese import ChinesePhonemizer

            voice._chinese_phonemizer = await asyncio.to_thread(
                _load_chinese_phonemizer,
                lambda: ChinesePhonemizer(voice.download_dir / "g2pW"),
            )
        # Prime ONNX session with a short synthesis
        await asyncio.to_thread(lambda: list(voice.synthesize(prime_text)))
        return voice
