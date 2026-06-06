"""Retrieve relevant chunks from the FAISS knowledge base."""

import hashlib
import logging
import os

import numpy as np
from .config import load_rag_config

logger = logging.getLogger(__name__)

STORE_DIR = load_rag_config().store_dir
_retrieval_cache: dict[str, list[dict]] = {}


def _query_hash(query: str, top_k: int, version: object) -> str:
    return hashlib.sha256(f"{query}::{top_k}::{version!r}".encode()).hexdigest()[:16]


async def retrieve(
    query: str,
    client,
    *,
    top_k: int = 5,
    model: str | None = None,
) -> list[dict]:
    """
    Retrieve top-K chunks from the knowledge base.
    Returns list of {doc, chunk, score, text}.
    """
    import faiss
    import resources
    from resources import require

    snapshot = await require(resources.faiss)
    refresh = getattr(resources.faiss, "refresh_if_changed", None)
    if refresh is not None:
        snapshot = await refresh()

    cache_key = _query_hash(query, top_k, snapshot.version)
    if cache_key in _retrieval_cache:
        logger.info("Retrieval cache hit for query hash %s", cache_key)
        return _retrieval_cache[cache_key]

    model = model or os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

    # Embed query
    resp = await client.embeddings.create(model=model, input=[query])
    q_vec = np.array([resp.data[0].embedding], dtype="float32")
    faiss.normalize_L2(q_vec)

    index = snapshot.index
    meta = snapshot.metadata

    actual_k = min(top_k, index.ntotal)
    if actual_k == 0:
        return []

    scores, indices = index.search(q_vec, actual_k)

    results = []
    for rank in range(actual_k):
        idx = int(indices[0][rank])
        if idx < 0:
            continue
        score = float(scores[0][rank])
        m = meta[idx]
        results.append({
            "doc": m["doc"],
            "chunk": m["chunk_index"],
            "score": round(score, 4),
            "text": m["text"],
        })

    _retrieval_cache[cache_key] = results
    logger.info("Retrieved %d chunks for query (len=%d)", len(results), len(query))
    return results
