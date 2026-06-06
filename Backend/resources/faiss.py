import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .base import ResourceProvider, ResourceStatus

logger = logging.getLogger(__name__)

SnapshotVersion = str


@dataclass(frozen=True)
class FaissSnapshot:
    index: Any
    metadata: tuple[dict, ...]
    version: SnapshotVersion


class FaissProvider(ResourceProvider[FaissSnapshot]):
    def __init__(self, store_dir: Path | None = None) -> None:
        super().__init__("faiss", required=False)
        if store_dir is None:
            from rag.config import load_rag_config

            store_dir = load_rag_config().store_dir
        self._store_dir = store_dir
        self._refresh_lock = asyncio.Lock()

    def _paths(self) -> tuple[Path, Path]:
        return self._store_dir / "kb.index", self._store_dir / "kb_meta.json"

    def _version_path(self) -> Path:
        index_path, _ = self._paths()
        return index_path.with_name("kb.version")

    @staticmethod
    def _file_version(path: Path) -> tuple[int, int]:
        stat = path.stat()
        return stat.st_mtime_ns, stat.st_size

    def _manifest(self, generation: str) -> dict[str, object]:
        index_path, meta_path = self._paths()
        return {
            "generation": generation,
            "index": self._file_version(index_path),
            "metadata": self._file_version(meta_path),
        }

    def _persisted_version(self) -> SnapshotVersion:
        version_path = self._version_path()
        if not version_path.exists():
            temp = version_path.with_suffix(f".{uuid.uuid4().hex}.tmp")
            try:
                temp.write_text(
                    json.dumps(self._manifest(uuid.uuid4().hex)),
                    encoding="utf-8",
                )
                os.replace(temp, version_path)
            finally:
                temp.unlink(missing_ok=True)
        try:
            manifest = json.loads(version_path.read_text(encoding="utf-8"))
            generation = str(manifest["generation"])
            expected_index = tuple(manifest["index"])
            expected_metadata = tuple(manifest["metadata"])
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            raise RuntimeError("FAISS version manifest is invalid") from exc
        index_path, meta_path = self._paths()
        if (
            self._file_version(index_path) != expected_index
            or self._file_version(meta_path) != expected_metadata
        ):
            raise RuntimeError("FAISS file pair is not committed")
        return generation

    def _load_snapshot(self) -> FaissSnapshot:
        import faiss

        index_path, meta_path = self._paths()
        if not index_path.exists() or not meta_path.exists():
            raise RuntimeError("FAISS index not found - run POST /ingest first")

        version = self._persisted_version()
        index = faiss.read_index(str(index_path))
        with open(meta_path, encoding="utf-8") as file:
            metadata = json.load(file)
        if not isinstance(metadata, list):
            raise RuntimeError("FAISS metadata must be a list")
        if getattr(index, "ntotal", len(metadata)) != len(metadata):
            raise RuntimeError("FAISS index and metadata are inconsistent")
        if self._persisted_version() != version:
            raise RuntimeError("FAISS snapshot changed while loading")
        return FaissSnapshot(
            index=index,
            metadata=tuple(metadata),
            version=version,
        )

    async def _load(self) -> FaissSnapshot:
        return await asyncio.to_thread(self._load_snapshot)

    def _replace_snapshot(self, snapshot: FaissSnapshot) -> None:
        self._instance = snapshot
        self._status = ResourceStatus.READY
        self._error = ""
        self._done.set()

    async def publish_snapshot(
        self,
        index: Any,
        metadata: list[dict],
    ) -> FaissSnapshot:
        async with self._refresh_lock:
            snapshot = FaissSnapshot(
                index=index,
                metadata=tuple(metadata),
                version=self._persisted_version(),
            )
            self._replace_snapshot(snapshot)
            return snapshot

    async def refresh_if_changed(self) -> FaissSnapshot:
        current = self.get()
        try:
            if self._persisted_version() == current.version:
                return current
        except Exception:
            logger.warning("event=faiss_snapshot_version_failed", exc_info=True)
            return current

        async with self._refresh_lock:
            current = self.get()
            try:
                if self._persisted_version() == current.version:
                    return current
                snapshot = await asyncio.to_thread(self._load_snapshot)
            except Exception:
                logger.warning("event=faiss_snapshot_refresh_failed", exc_info=True)
                return current
            self._replace_snapshot(snapshot)
            return snapshot
