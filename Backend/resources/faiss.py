import asyncio

from .base import ResourceProvider


class FaissProvider(ResourceProvider):
    def __init__(self) -> None:
        super().__init__("faiss", required=False)

    async def _load(self):
        import json
        import faiss
        from rag import retrieve as _r

        index_path = _r.STORE_DIR / "kb.index"
        meta_path  = _r.STORE_DIR / "kb_meta.json"

        if not index_path.exists() or not meta_path.exists():
            raise RuntimeError("FAISS index not found — run POST /ingest first")

        def _load_sync():
            index = faiss.read_index(str(index_path))
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
            # Populate retrieve module cache so first real query is instant
            _r._faiss_index       = index
            _r._faiss_meta        = meta
            _r._faiss_index_mtime = index_path.stat().st_mtime
            _r._faiss_meta_mtime  = meta_path.stat().st_mtime
            return index

        return await asyncio.to_thread(_load_sync)
