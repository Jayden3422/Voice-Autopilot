import asyncio
import json
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from resources.base import ResourceFailed, ResourceProvider


class FakeProvider(ResourceProvider):
    async def _load(self):
        return object()


@pytest.mark.asyncio
async def test_openai_dependency_waits_for_provider(monkeypatch):
    import ai_client
    import resources

    client = object()
    provider = FakeProvider("openai")
    monkeypatch.setattr(resources, "openai", provider)

    task = asyncio.create_task(ai_client.get_openai_client())
    await asyncio.sleep(0)
    assert not task.done()

    provider.mark_ready(client)
    assert await task is client


@pytest.mark.asyncio
async def test_async_transcription_waits_for_whisper_provider(monkeypatch):
    import resources
    from speech import speech

    provider = FakeProvider("whisper_stt")
    monkeypatch.setattr(resources, "whisper", provider)
    monkeypatch.setattr(speech, "transcribe_audio", lambda path, lang="zh": "ready")

    task = asyncio.create_task(speech.transcribe_audio_base64("", lang="en"))
    await asyncio.sleep(0)
    assert not task.done()

    provider.mark_ready(object())
    assert await task == "ready"


@pytest.mark.asyncio
async def test_async_file_transcription_waits_for_whisper_provider(monkeypatch):
    import resources
    from speech import speech

    provider = FakeProvider("whisper_stt")
    monkeypatch.setattr(resources, "whisper", provider)
    monkeypatch.setattr(speech, "transcribe_audio", lambda path, lang="zh": "ready")

    task = asyncio.create_task(speech.transcribe_audio_async("audio.webm", lang="en"))
    await asyncio.sleep(0)
    assert not task.done()

    provider.mark_ready(object())
    assert await task == "ready"


@pytest.mark.asyncio
async def test_async_synthesis_waits_for_piper_provider(monkeypatch):
    import resources
    from speech import speech

    provider = FakeProvider("piper_tts_en")
    monkeypatch.setattr(resources, "piper_en", provider)
    monkeypatch.setattr(speech, "_synthesize_speech_sync", lambda text, lang="zh": b"wav")

    task = asyncio.create_task(speech.synthesize_speech("Hello", lang="en"))
    await asyncio.sleep(0)
    assert not task.done()

    provider.mark_ready(object())
    assert await task == b"wav"


@pytest.mark.asyncio
async def test_piper_provider_passes_use_cuda_as_keyword(monkeypatch, tmp_path):
    from resources.piper import PiperProvider

    model_path = tmp_path / "voice.onnx"
    load_args = {}

    class FakeVoice:
        @staticmethod
        def load(path, config_path=None, use_cuda=False):
            load_args.update(
                path=path,
                config_path=config_path,
                use_cuda=use_cuda,
            )
            return SimpleNamespace(synthesize=lambda _text: [object()])

    monkeypatch.setitem(sys.modules, "piper", SimpleNamespace(PiperVoice=FakeVoice))
    monkeypatch.setenv("PIPER_EN_MODEL", str(model_path))

    await PiperProvider("en")._load()

    assert load_args == {
        "path": str(model_path),
        "config_path": None,
        "use_cuda": False,
    }


def test_piper_disables_g2pw_graph_optimization(monkeypatch):
    from resources.piper import _load_chinese_phonemizer

    optimization_levels = []

    class SessionOptions:
        graph_optimization_level = "enable_all"

    class FakeOrt:
        class GraphOptimizationLevel:
            ORT_DISABLE_ALL = "disable_all"

        @staticmethod
        def InferenceSession(_path, sess_options=None):
            optimization_levels.append(sess_options.graph_optimization_level)
            return object()

    class FakeG2PWConverter:
        def __init__(self):
            options = SessionOptions()
            options.graph_optimization_level = "enable_all"
            FakeOrt.InferenceSession("g2pw.onnx", sess_options=options)

    monkeypatch.setitem(
        sys.modules,
        "g2pw.api",
        SimpleNamespace(onnxruntime=FakeOrt),
    )

    _load_chinese_phonemizer(FakeG2PWConverter)

    assert optimization_levels == ["disable_all"]


@pytest.mark.asyncio
async def test_retrieve_waits_for_faiss_provider(monkeypatch, tmp_path):
    import resources
    from rag import retrieve as retrieve_module
    from resources.faiss import FaissSnapshot

    provider = FakeProvider("faiss")
    monkeypatch.setattr(resources, "faiss", provider)

    (tmp_path / "kb.index").write_bytes(b"index")
    (tmp_path / "kb_meta.json").write_text(
        json.dumps([{"doc": "doc.md", "chunk_index": 0, "text": "answer"}]),
        encoding="utf-8",
    )
    monkeypatch.setattr(retrieve_module, "STORE_DIR", tmp_path)
    monkeypatch.setattr(retrieve_module, "_retrieval_cache", {})

    class FakeIndex:
        ntotal = 1

        def search(self, vector, top_k):
            return np.array([[0.9]], dtype="float32"), np.array([[0]], dtype="int64")

    index = FakeIndex()
    monkeypatch.setitem(
        sys.modules,
        "faiss",
        SimpleNamespace(normalize_L2=lambda vector: None),
    )

    embeddings_called = asyncio.Event()

    class Embeddings:
        async def create(self, **kwargs):
            embeddings_called.set()
            return SimpleNamespace(
                data=[SimpleNamespace(embedding=[0.1, 0.2])]
            )

    client = SimpleNamespace(embeddings=Embeddings())
    task = asyncio.create_task(retrieve_module.retrieve("question", client, top_k=1))
    await asyncio.sleep(0)

    assert not embeddings_called.is_set()
    provider.mark_ready(FaissSnapshot(
        index=index,
        metadata=({"doc": "doc.md", "chunk_index": 0, "text": "answer"},),
        version=((1, 1), (1, 1)),
    ))

    assert await task == [
        {
            "doc": "doc.md",
            "chunk": 0,
            "score": pytest.approx(0.9, abs=0.0001),
            "text": "answer",
        }
    ]


@pytest.mark.asyncio
async def test_tts_route_preserves_resource_failed(monkeypatch):
    from api import voice

    async def unavailable(*args, **kwargs):
        raise ResourceFailed("piper unavailable")

    monkeypatch.setattr(voice, "synthesize_speech", unavailable)

    with pytest.raises(ResourceFailed, match="piper unavailable"):
        await voice.tts(voice.TTSRequest(text="Hello", lang="en"))


@pytest.mark.asyncio
async def test_autopilot_route_preserves_resource_failed(monkeypatch):
    from api import autopilot

    async def unavailable(*args, **kwargs):
        raise ResourceFailed("openai unavailable")

    monkeypatch.setattr(autopilot, "create_run", lambda *args, **kwargs: None)
    monkeypatch.setattr(autopilot, "update_run", lambda *args, **kwargs: None)
    monkeypatch.setattr(autopilot, "extract_autopilot_json", unavailable)
    request = SimpleNamespace(mode="text", text="hello", audio_base64=None, locale="en")

    with pytest.raises(ResourceFailed, match="openai unavailable"):
        await autopilot.autopilot_run(request, object())
