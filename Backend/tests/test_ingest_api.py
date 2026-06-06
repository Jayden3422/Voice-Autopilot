import pytest
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_ingest_endpoint_maps_contention_to_409(monkeypatch):
    from api import autopilot
    from rag.ingest_lock import IngestInProgress

    async def contended(client):
        raise IngestInProgress("busy")

    import rag.ingest

    monkeypatch.setattr(rag.ingest, "ingest_knowledge_base", contended)

    with pytest.raises(HTTPException) as exc_info:
        await autopilot.autopilot_ingest(object())

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == {"error": "ingest_in_progress"}
