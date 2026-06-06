import multiprocessing

import pytest


def _hold_lock(path: str, acquired, release) -> None:
    from rag.ingest_lock import IngestFileLock

    with IngestFileLock(path):
        acquired.set()
        release.wait(timeout=5)


def test_second_lock_in_same_process_fails_immediately(tmp_path):
    from rag.ingest_lock import IngestFileLock, IngestInProgress

    lock_path = tmp_path / "ingest.lock"
    with IngestFileLock(lock_path):
        with pytest.raises(IngestInProgress):
            with IngestFileLock(lock_path):
                pass


def test_parent_cannot_acquire_while_child_owns_lock(tmp_path):
    from rag.ingest_lock import IngestFileLock, IngestInProgress

    lock_path = tmp_path / "ingest.lock"
    acquired = multiprocessing.Event()
    release = multiprocessing.Event()
    process = multiprocessing.Process(
        target=_hold_lock,
        args=(str(lock_path), acquired, release),
    )
    process.start()
    try:
        assert acquired.wait(timeout=5)
        with pytest.raises(IngestInProgress):
            with IngestFileLock(lock_path):
                pass
    finally:
        release.set()
        process.join(timeout=5)
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)


def test_lock_can_be_acquired_after_owner_exits(tmp_path):
    from rag.ingest_lock import IngestFileLock

    lock_path = tmp_path / "ingest.lock"
    acquired = multiprocessing.Event()
    release = multiprocessing.Event()
    process = multiprocessing.Process(
        target=_hold_lock,
        args=(str(lock_path), acquired, release),
    )
    process.start()
    assert acquired.wait(timeout=5)
    release.set()
    process.join(timeout=5)
    assert process.exitcode == 0

    with IngestFileLock(lock_path):
        pass


def test_lock_releases_when_context_body_raises(tmp_path):
    from rag.ingest_lock import IngestFileLock

    lock_path = tmp_path / "ingest.lock"
    with pytest.raises(RuntimeError, match="boom"):
        with IngestFileLock(lock_path):
            raise RuntimeError("boom")

    with IngestFileLock(lock_path):
        pass
