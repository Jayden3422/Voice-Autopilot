import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from resources.faiss import FaissProvider, FaissSnapshot


class FakeIndex:
    def __init__(self, marker: int):
        self.marker = marker
        self.ntotal = 1

    def search(self, vector, top_k):
        return (
            np.array([[float(self.marker)]], dtype="float32"),
            np.array([[0]], dtype="int64"),
        )


def install_fake_faiss(monkeypatch):
    monkeypatch.setitem(
        sys.modules,
        "faiss",
        SimpleNamespace(
            read_index=lambda path: FakeIndex(int(Path(path).read_text(encoding="utf-8"))),
            normalize_L2=lambda matrix: None,
        ),
    )


def write_store(store_dir: Path, marker: int, text: str) -> None:
    store_dir.mkdir(parents=True, exist_ok=True)
    (store_dir / "kb.index").write_text(str(marker), encoding="utf-8")
    (store_dir / "kb_meta.json").write_text(
        json.dumps([{"doc": "doc.md", "chunk_index": 0, "text": text}]),
        encoding="utf-8",
    )
    write_manifest(store_dir, f"{marker}:{text}")


def write_manifest(store_dir: Path, generation: str) -> None:
    index_stat = (store_dir / "kb.index").stat()
    meta_stat = (store_dir / "kb_meta.json").stat()
    (store_dir / "kb.version").write_text(
        json.dumps({
            "generation": generation,
            "index": [index_stat.st_mtime_ns, index_stat.st_size],
            "metadata": [meta_stat.st_mtime_ns, meta_stat.st_size],
        }),
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_faiss_provider_loads_complete_snapshot_and_refreshes_changed_files(
    monkeypatch, tmp_path
):
    install_fake_faiss(monkeypatch)
    write_store(tmp_path, 1, "old")
    provider = FaissProvider(store_dir=tmp_path)
    provider.mark_ready(await provider.initialize())

    first = provider.get()
    assert isinstance(first, FaissSnapshot)
    assert first.index.marker == 1
    assert first.metadata[0]["text"] == "old"

    write_store(tmp_path, 22, "new value")
    second = await provider.refresh_if_changed()

    assert second is provider.get()
    assert second is not first
    assert second.index.marker == 22
    assert second.metadata[0]["text"] == "new value"


@pytest.mark.asyncio
async def test_faiss_refresh_failure_preserves_last_usable_snapshot(monkeypatch, tmp_path):
    install_fake_faiss(monkeypatch)
    write_store(tmp_path, 1, "old")
    provider = FaissProvider(store_dir=tmp_path)
    provider.mark_ready(await provider.initialize())
    first = provider.get()

    write_store(tmp_path, 22, "new value")
    monkeypatch.setitem(
        sys.modules,
        "faiss",
        SimpleNamespace(
            read_index=lambda path: (_ for _ in ()).throw(RuntimeError("broken")),
        ),
    )

    assert await provider.refresh_if_changed() is first
    assert provider.get() is first


@pytest.mark.asyncio
async def test_faiss_refresh_waits_for_committed_file_pair(monkeypatch, tmp_path):
    install_fake_faiss(monkeypatch)
    write_store(tmp_path, 1, "old")
    provider = FaissProvider(store_dir=tmp_path)
    provider.mark_ready(await provider.initialize())
    first = provider.get()

    (tmp_path / "kb.index").write_text("22", encoding="utf-8")
    (tmp_path / "kb_meta.json").write_text(
        json.dumps([{"doc": "doc.md", "chunk_index": 0, "text": "new value"}]),
        encoding="utf-8",
    )

    assert await provider.refresh_if_changed() is first

    write_manifest(tmp_path, "22:new value")
    second = await provider.refresh_if_changed()
    assert second.index.marker == 22
    assert second.metadata[0]["text"] == "new value"


@pytest.mark.asyncio
async def test_faiss_initial_load_rejects_uncommitted_file_pair(monkeypatch, tmp_path):
    install_fake_faiss(monkeypatch)
    write_store(tmp_path, 1, "old")
    (tmp_path / "kb.index").write_text("22", encoding="utf-8")

    with pytest.raises(RuntimeError, match="not committed"):
        await FaissProvider(store_dir=tmp_path).initialize()


@pytest.mark.asyncio
async def test_retrieve_cache_is_scoped_to_snapshot_version(monkeypatch, tmp_path):
    import resources
    from rag import retrieve as retrieve_module

    install_fake_faiss(monkeypatch)
    write_store(tmp_path, 1, "old")
    provider = FaissProvider(store_dir=tmp_path)
    provider.mark_ready(await provider.initialize())
    monkeypatch.setattr(resources, "faiss", provider)
    monkeypatch.setattr(retrieve_module, "_retrieval_cache", {})

    class Embeddings:
        async def create(self, **kwargs):
            return SimpleNamespace(data=[SimpleNamespace(embedding=[0.1, 0.2])])

    client = SimpleNamespace(embeddings=Embeddings())
    first = await retrieve_module.retrieve("question", client, top_k=1)

    write_store(tmp_path, 22, "new value")
    second = await retrieve_module.retrieve("question", client, top_k=1)

    assert first[0]["text"] == "old"
    assert first[0]["score"] == pytest.approx(1.0)
    assert second[0]["text"] == "new value"
    assert second[0]["score"] == pytest.approx(22.0)


@pytest.mark.asyncio
async def test_ingest_publishes_complete_snapshot_to_current_process(
    monkeypatch, tmp_path
):
    import resources
    from rag import ingest

    kb_dir = tmp_path / "kb"
    store_dir = tmp_path / "store"
    kb_dir.mkdir()
    (kb_dir / "doc.md").write_text("knowledge", encoding="utf-8")
    monkeypatch.setattr(ingest, "KB_DIR", kb_dir)
    monkeypatch.setattr(ingest, "STORE_DIR", store_dir)
    monkeypatch.setattr(ingest, "EMBED_CACHE_PATH", store_dir / "embed_cache.json")
    monkeypatch.setattr(ingest, "_embed_texts", lambda texts, client: _async_value([[0.1, 0.2]]))

    published = []

    class Provider:
        async def publish_snapshot(self, index, metadata):
            published.append((index, metadata))

    monkeypatch.setattr(resources, "faiss", Provider())

    class Index:
        ntotal = 0

        def add(self, matrix):
            self.ntotal = len(matrix)

    def write_index(index, path):
        Path(path).write_text("index", encoding="utf-8")

    monkeypatch.setitem(
        sys.modules,
        "faiss",
        SimpleNamespace(
            normalize_L2=lambda matrix: None,
            IndexFlatIP=lambda dim: Index(),
            write_index=write_index,
        ),
    )

    result = await ingest.ingest_knowledge_base(object())

    assert result == {"documents": 1, "chunks": 1}
    assert len(published) == 1
    assert published[0][1] == [
        {"doc": "doc.md", "chunk_index": 0, "text": "knowledge"}
    ]
    assert not list(store_dir.glob("*.tmp"))


@pytest.mark.asyncio
async def test_ingest_contention_does_not_read_or_embed(monkeypatch, tmp_path):
    from rag import ingest
    from rag.ingest_lock import IngestFileLock, IngestInProgress

    store_dir = tmp_path / "store"
    kb_dir = tmp_path / "kb"
    kb_dir.mkdir()
    (kb_dir / "doc.md").write_text("knowledge", encoding="utf-8")
    monkeypatch.setattr(ingest, "STORE_DIR", store_dir)
    monkeypatch.setattr(ingest, "KB_DIR", kb_dir)

    embedded = False

    async def embed(*args, **kwargs):
        nonlocal embedded
        embedded = True
        return [[0.1, 0.2]]

    monkeypatch.setattr(ingest, "_embed_texts", embed)

    with IngestFileLock(store_dir / "ingest.lock"):
        with pytest.raises(IngestInProgress):
            await ingest.ingest_knowledge_base(object())

    assert embedded is False
    assert not (store_dir / "kb.index").exists()


async def _async_value(value):
    return value
