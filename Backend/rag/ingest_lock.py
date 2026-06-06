from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import BinaryIO

logger = logging.getLogger(__name__)


class IngestInProgress(RuntimeError):
    """Raised when another process already owns the ingest lock."""


class IngestFileLock:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._file: BinaryIO | None = None

    def __enter__(self) -> "IngestFileLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        file = open(self.path, "a+b")
        try:
            if os.name == "nt":
                self._acquire_windows(file)
            else:
                self._acquire_posix(file)
        except IngestInProgress:
            file.close()
            logger.info("event=ingest_lock_contended path=%s", self.path)
            raise
        except Exception:
            file.close()
            raise
        self._file = file
        logger.info("event=ingest_lock_acquired path=%s", self.path)
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        file = self._file
        self._file = None
        if file is None:
            return
        try:
            if os.name == "nt":
                self._release_windows(file)
            else:
                self._release_posix(file)
        finally:
            file.close()
            logger.info("event=ingest_lock_released path=%s", self.path)

    @staticmethod
    def _acquire_windows(file: BinaryIO) -> None:
        import msvcrt

        file.seek(0, os.SEEK_END)
        if file.tell() == 0:
            file.seek(0)
            file.write(b"\0")
            file.flush()
        file.seek(0)
        try:
            msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise IngestInProgress("knowledge-base ingest is already running") from exc

    @staticmethod
    def _release_windows(file: BinaryIO) -> None:
        import msvcrt

        file.seek(0)
        msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, 1)

    @staticmethod
    def _acquire_posix(file: BinaryIO) -> None:
        import fcntl

        try:
            fcntl.flock(file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise IngestInProgress("knowledge-base ingest is already running") from exc

    @staticmethod
    def _release_posix(file: BinaryIO) -> None:
        import fcntl

        fcntl.flock(file.fileno(), fcntl.LOCK_UN)
