"""Ingest markdown knowledge base files into a FAISS vector store."""

import hashlib
import json
import logging
import os
import re
import uuid
from pathlib import Path

import numpy as np
from .config import load_rag_config

logger = logging.getLogger(__name__)

KB_DIR = Path(__file__).resolve().parent.parent.parent / "knowledge_base"
STORE_DIR = load_rag_config().store_dir
EMBED_CACHE_PATH = STORE_DIR / "embed_cache.json"
CHUNK_SIZE = 600  # target characters per chunk
CHUNK_OVERLAP = 100


def _ensure_dirs():
    STORE_DIR.mkdir(parents=True, exist_ok=True)


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks by paragraph boundaries."""
    paragraphs = re.split(r"\n{2,}", text.strip())
    chunks = []
    current = ""
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(current) + len(para) + 2 > chunk_size and current:
            chunks.append(current.strip())
            # Keep overlap from the end of current chunk
            if overlap > 0 and len(current) > overlap:
                current = current[-overlap:] + "\n\n" + para
            else:
                current = para
        else:
            current = current + "\n\n" + para if current else para
    if current.strip():
        chunks.append(current.strip())
    return chunks if chunks else [text.strip()]


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _load_embed_cache() -> dict:
    if EMBED_CACHE_PATH.exists():
        try:
            with open(EMBED_CACHE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_embed_cache(cache: dict):
    _ensure_dirs()
    with open(EMBED_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f)


async def _embed_texts(texts: list[str], client, model: str | None = None) -> list[list[float]]:
    """Embed texts using OpenAI API with caching."""
    model = model or os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    cache = _load_embed_cache()
    results = [None] * len(texts)
    to_embed = []
    to_embed_idx = []

    for i, t in enumerate(texts):
        h = _text_hash(t)
        if h in cache:
            results[i] = cache[h]
        else:
            to_embed.append(t)
            to_embed_idx.append(i)

    if to_embed:
        logger.info("Embedding %d new chunks (cache hit: %d)", len(to_embed), len(texts) - len(to_embed))
        # Batch embed in groups of 100
        for batch_start in range(0, len(to_embed), 100):
            batch = to_embed[batch_start:batch_start + 100]
            resp = await client.embeddings.create(model=model, input=batch)
            for j, emb_data in enumerate(resp.data):
                idx = to_embed_idx[batch_start + j]
                results[idx] = emb_data.embedding
                cache[_text_hash(to_embed[batch_start + j])] = emb_data.embedding
        _save_embed_cache(cache)

    return results


async def _ingest_knowledge_base_locked(client) -> dict:
    """
    Read all .md files from knowledge_base/, chunk, embed, and save to FAISS index.
    Returns metadata about ingested documents.
    """
    import faiss

    _ensure_dirs()

    md_files = sorted(KB_DIR.glob("*.md"))
    if not md_files:
        logger.warning("No .md files found in %s", KB_DIR)
        return {"documents": 0, "chunks": 0}

    all_chunks = []
    chunk_meta = []  # [{doc, chunk_index, text}]

    for md_file in md_files:
        text = md_file.read_text(encoding="utf-8")
        doc_name = md_file.name
        chunks = _chunk_text(text)
        for i, chunk in enumerate(chunks):
            all_chunks.append(chunk)
            chunk_meta.append({"doc": doc_name, "chunk_index": i, "text": chunk})

    logger.info("Ingesting %d chunks from %d documents", len(all_chunks), len(md_files))

    embeddings = await _embed_texts(all_chunks, client)
    dim = len(embeddings[0])
    matrix = np.array(embeddings, dtype="float32")

    # Normalize for cosine similarity
    faiss.normalize_L2(matrix)
    index = faiss.IndexFlatIP(dim)
    index.add(matrix)

    # Persist complete artifacts before publishing the new in-memory snapshot.
    index_path = STORE_DIR / "kb.index"
    meta_path = STORE_DIR / "kb_meta.json"
    version_path = STORE_DIR / "kb.version"
    index_temp = STORE_DIR / f"kb.index.{uuid.uuid4().hex}.tmp"
    meta_temp = STORE_DIR / f"kb_meta.json.{uuid.uuid4().hex}.tmp"
    version_temp = STORE_DIR / f"kb.version.{uuid.uuid4().hex}.tmp"
    try:
        faiss.write_index(index, str(index_temp))
        with open(meta_temp, "w", encoding="utf-8") as file:
            json.dump(chunk_meta, file, ensure_ascii=False, indent=2)
        os.replace(index_temp, index_path)
        os.replace(meta_temp, meta_path)
        index_stat = index_path.stat()
        meta_stat = meta_path.stat()
        version_temp.write_text(
            json.dumps({
                "generation": uuid.uuid4().hex,
                "index": [index_stat.st_mtime_ns, index_stat.st_size],
                "metadata": [meta_stat.st_mtime_ns, meta_stat.st_size],
            }),
            encoding="utf-8",
        )
        os.replace(version_temp, version_path)
    finally:
        index_temp.unlink(missing_ok=True)
        meta_temp.unlink(missing_ok=True)
        version_temp.unlink(missing_ok=True)

    import resources

    await resources.faiss.publish_snapshot(index, chunk_meta)

    logger.info("FAISS index saved: dim=%d, vectors=%d", dim, index.ntotal)
    return {"documents": len(md_files), "chunks": len(all_chunks)}


async def ingest_knowledge_base(client) -> dict:
    """Run one same-host ingest writer or fail immediately on contention."""
    from .ingest_lock import IngestFileLock

    with IngestFileLock(STORE_DIR / "ingest.lock"):
        return await _ingest_knowledge_base_locked(client)
