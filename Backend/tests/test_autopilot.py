"""Minimal tests for the autopilot system."""

import json
import sys
from pathlib import Path

import pytest

# Add Backend to path so imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# --- Test 1: Schema validation ---

def test_schema_validation_valid():
    """A valid extraction output should pass schema validation."""
    import jsonschema
    from chat.autopilot_extractor import _load_schema, _validate

    schema = _load_schema("autopilot_schema.json")

    valid_data = {
        "conversation_language": "en",
        "intent": "sales_lead",
        "urgency": "medium",
        "budget": None,
        "product_interest": ["voice assistant"],
        "entities": {
            "company": "Acme Corp",
            "contact_name": "John",
            "email": None,
            "phone": None,
        },
        "summary": "Customer is interested in voice assistant for sales team.",
        "next_best_actions": [
            {
                "action_type": "send_slack_summary",
                "requires_confirmation": True,
                "confidence": 0.9,
                "payload": {"channel": "#sales", "message": "New lead from Acme Corp"},
            }
        ],
        "follow_up_questions": ["What is your team size?"],
        "confidence_notes": [],
    }

    # Should not raise
    _validate(valid_data, schema)


def test_schema_validation_invalid():
    """An invalid extraction output should fail schema validation."""
    import jsonschema
    from chat.autopilot_extractor import _load_schema, _validate

    schema = _load_schema("autopilot_schema.json")

    invalid_data = {
        "intent": "invalid_intent_type",
        "summary": "test",
        "next_best_actions": [],
    }

    with pytest.raises(jsonschema.ValidationError):
        _validate(invalid_data, schema)


def test_schema_validation_missing_required():
    """Missing required fields should fail validation."""
    import jsonschema
    from chat.autopilot_extractor import _load_schema, _validate

    schema = _load_schema("autopilot_schema.json")

    # Missing 'summary' and 'next_best_actions'
    incomplete_data = {"intent": "sales_lead"}

    with pytest.raises(jsonschema.ValidationError):
        _validate(incomplete_data, schema)


# --- Test 2: RAG ingest/retrieve (file-based, no API) ---

def test_knowledge_base_files_exist():
    """Knowledge base should have markdown files for RAG."""
    kb_dir = Path(__file__).resolve().parent.parent.parent / "knowledge_base"
    md_files = list(kb_dir.glob("*.md"))
    assert len(md_files) >= 10, f"Expected >= 10 knowledge base files, found {len(md_files)}"


def test_chunk_text():
    """Text chunking should produce non-empty chunks."""
    from rag.ingest import _chunk_text

    text = """
# Introduction

This is a test document about our product.

## Features

Our product has many great features including voice recognition,
natural language processing, and calendar integration.

## Pricing

We offer three plans: Starter at $29/mo, Pro at $99/mo, and Enterprise
with custom pricing. Each plan includes different levels of support.

## FAQ

Q: How do I get started?
A: Sign up on our website and follow the onboarding guide.

Q: What languages are supported?
A: We support English and Chinese with more languages coming soon.
"""
    chunks = _chunk_text(text, chunk_size=200, overlap=50)
    assert len(chunks) >= 2, f"Expected >= 2 chunks, got {len(chunks)}"
    for chunk in chunks:
        assert len(chunk.strip()) > 0, "Chunk should not be empty"


# --- Test 3: Actions dry_run ---

@pytest.mark.asyncio
async def test_slack_dry_run():
    """Slack dry_run should return a preview without sending."""
    from connectors.slack import dry_run

    result = await dry_run({
        "channel": "#sales",
        "message": "New lead: Acme Corp interested in voice assistant",
    })
    assert "preview" in result
    assert "#sales" in result["preview"]
    assert result["channel"] == "#sales"


@pytest.mark.asyncio
async def test_linear_dry_run():
    """Linear dry_run should return a preview without creating an issue."""
    from connectors.linear import dry_run

    result = await dry_run({
        "title": "Bug: Login form crashes on submit",
        "description": "User reported that the login form crashes when clicking submit.",
        "priority": "high",
    })
    assert "preview" in result
    assert "Bug" in result["preview"]
    assert result["priority"] == "high"


@pytest.mark.asyncio
async def test_email_dry_run():
    """Email dry_run should return a preview without sending."""
    from connectors.email_connector import dry_run

    result = await dry_run({
        "to": "customer@example.com",
        "subject": "Follow-up: Your inquiry",
        "body": "Thank you for your interest in our product.",
    })
    assert "preview" in result
    assert "customer@example.com" in result["preview"]


@pytest.mark.asyncio
async def test_dispatcher_dry_run():
    """Dispatcher should route dry_run to the correct connector."""
    from actions.dispatcher import dry_run_action

    action = {
        "action_type": "send_slack_summary",
        "requires_confirmation": True,
        "confidence": 0.85,
        "payload": {"message": "Test summary"},
    }
    result = await dry_run_action(action)
    assert "preview" in result


@pytest.mark.asyncio
async def test_calendar_preview():
    """Calendar dry_run should generate a preview."""
    from actions.dispatcher import dry_run_action

    action = {
        "action_type": "create_meeting",
        "requires_confirmation": True,
        "confidence": 0.9,
        "payload": {
            "title": "Team Standup",
            "date": "2025-01-15",
            "start_time": "10:00",
            "end_time": "10:30",
            "attendees": ["alice@example.com"],
        },
    }
    result = await dry_run_action(action)
    assert "preview" in result
    assert "Team Standup" in result["preview"]


@pytest.mark.asyncio
async def test_none_action_dry_run():
    """Action type 'none' should return a simple preview."""
    from actions.dispatcher import dry_run_action

    result = await dry_run_action({"action_type": "none", "payload": {}})
    assert "preview" in result


# --- Test: SQLite store ---

def test_sqlite_runs_crud():
    """SQLite runs table should support create, update, and get."""
    import uuid
    from store.runs import create_run, update_run, get_run

    run_id = str(uuid.uuid4())
    create_run(run_id, "text", "Hello, I need help")

    run = get_run(run_id)
    assert run is not None
    assert run["run_id"] == run_id
    assert run["status"] == "pending"

    update_run(run_id, transcript="Hello, I need help", status="transcribed")
    run = get_run(run_id)
    assert run["transcript"] == "Hello, I need help"
    assert run["status"] == "transcribed"

    update_run(
        run_id,
        extracted_json={"intent": "support_issue", "summary": "test", "next_best_actions": []},
        status="extracted",
    )
    run = get_run(run_id)
    assert run["extracted_json"]["intent"] == "support_issue"
