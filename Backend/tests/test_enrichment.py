"""Tests for actions/enrichment.py — action enrichment and orchestration helpers."""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from actions.enrichment import (
    append_confirmation_to_email_payload,
    append_confirmation_to_slack_payload,
    build_rag_query,
    determine_final_status,
    merge_extracted_actions,
)

REF = datetime(2026, 6, 10, 9, 0)


# ── build_rag_query ───────────────────────────────────────────────────────────

def test_build_rag_query_combines_intent_product_and_summary():
    """Query string combines intent, product interest, and summary."""
    extracted = {
        "intent": "sales_lead",
        "product_interest": ["voice assistant"],
        "summary": "Customer wants automation",
    }
    q = build_rag_query(extracted)
    assert "sales lead" in q
    assert "voice assistant" in q
    assert "Customer wants automation" in q


def test_build_rag_query_empty_falls_back_to_general():
    """Empty extracted dict returns 'general inquiry'."""
    assert build_rag_query({}) == "general inquiry"


def test_build_rag_query_partial_fields():
    """Query uses only the fields that are present."""
    q = build_rag_query({"intent": "support_issue"})
    assert "support issue" in q
    assert "general inquiry" not in q


# ── enrich_actions ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_enrich_actions_always_injects_slack():
    """A slack summary action is always added even when the action list is empty."""
    from actions.enrichment import enrich_actions

    with patch("utils.timezone.now", return_value=REF):
        result = await enrich_actions([], {"summary": "test", "conversation_language": "en"}, {})

    assert any(a["action_type"] == "send_slack_summary" for a in result)


@pytest.mark.asyncio
async def test_enrich_actions_adds_email_when_entity_has_address():
    """Email action is added automatically when the extracted entities include an email."""
    from actions.enrichment import enrich_actions

    extracted = {
        "summary": "test",
        "conversation_language": "en",
        "entities": {"email": "client@example.com"},
    }
    with patch("utils.timezone.now", return_value=REF):
        result = await enrich_actions([], extracted, {})

    email_actions = [a for a in result if a["action_type"] == "send_email_followup"]
    assert len(email_actions) == 1
    assert email_actions[0]["payload"]["to"] == "client@example.com"


@pytest.mark.asyncio
async def test_enrich_actions_skips_email_without_address():
    """Email action is not injected when no email address is in the entities."""
    from actions.enrichment import enrich_actions

    extracted = {"summary": "test", "conversation_language": "en", "entities": {}}
    with patch("utils.timezone.now", return_value=REF):
        result = await enrich_actions([], extracted, {})

    assert not any(a["action_type"] == "send_email_followup" for a in result)


@pytest.mark.asyncio
async def test_enrich_actions_ticket_inherits_urgency_as_priority():
    """create_ticket without a priority inherits it from the urgency field."""
    from actions.enrichment import enrich_actions

    actions = [
        {"action_type": "create_ticket", "payload": {}, "confidence": 0.9, "requires_confirmation": True}
    ]
    extracted = {
        "summary": "System down",
        "conversation_language": "en",
        "urgency": "high",
        "entities": {},
    }
    with patch("utils.timezone.now", return_value=REF):
        result = await enrich_actions(actions, extracted, {})

    ticket = next(a for a in result if a["action_type"] == "create_ticket")
    assert ticket["payload"]["priority"] == "high"


@pytest.mark.asyncio
async def test_enrich_actions_fills_slack_with_company_and_summary():
    """Slack payload is populated with company name and summary from extracted data."""
    from actions.enrichment import enrich_actions

    extracted = {
        "summary": "New enterprise lead",
        "conversation_language": "en",
        "intent": "sales_lead",
        "urgency": "high",
        "entities": {"company": "BigCo"},
    }
    with patch("utils.timezone.now", return_value=REF):
        result = await enrich_actions([], extracted, {})

    slack = next(a for a in result if a["action_type"] == "send_slack_summary")
    assert slack["payload"]["channel"] == "#general"
    assert "BigCo" in slack["payload"]["message"]


# ── append_confirmation_to_slack_payload ──────────────────────────────────────

def test_append_confirmation_to_slack_appends_after_existing_message():
    """Confirmation text is appended after the existing message."""
    payload = {"message": "Lead from Acme"}
    append_confirmation_to_slack_payload(payload, "Calendar created: Standup on 2026-06-15.")
    assert "Lead from Acme" in payload["message"]
    assert "Calendar created" in payload["message"]


def test_append_confirmation_to_slack_empty_message():
    """Confirmation becomes the entire message when the payload message is empty."""
    payload = {"message": ""}
    append_confirmation_to_slack_payload(payload, "Calendar created.")
    assert payload["message"] == "Calendar created."


# ── append_confirmation_to_email_payload ──────────────────────────────────────

def test_append_confirmation_to_email_appends_to_body_text_and_html():
    """Confirmation is appended to both body_text and body_html."""
    payload = {"body_text": "Dear Client,\n\nThank you.", "body_html": "<p>Dear Client</p>"}
    append_confirmation_to_email_payload(payload, "Meeting confirmed.", "<p>Meeting confirmed.</p>")
    assert "Meeting confirmed." in payload["body_text"]
    assert "Meeting confirmed." in payload["body_html"]


# ── merge_extracted_actions ───────────────────────────────────────────────────

def test_merge_extracted_actions_updates_matching_payload():
    """Enriched payload fields are merged back into the matching extracted action."""
    extracted = {
        "next_best_actions": [
            {"action_type": "send_slack_summary", "payload": {"channel": "#general"}},
        ]
    }
    enriched = [
        {"action_type": "send_slack_summary", "payload": {"channel": "#general", "message": "filled"}},
    ]
    merged = merge_extracted_actions(extracted, enriched)
    assert merged["next_best_actions"][0]["payload"]["message"] == "filled"


def test_merge_extracted_actions_does_not_mutate_input():
    """The original extracted dict is not modified."""
    extracted = {"next_best_actions": [{"action_type": "create_ticket", "payload": {}}]}
    enriched = [{"action_type": "create_ticket", "payload": {"title": "Bug"}}]
    merge_extracted_actions(extracted, enriched)
    assert extracted["next_best_actions"][0]["payload"] == {}


# ── determine_final_status ────────────────────────────────────────────────────

def test_determine_final_status_all_skipped_returns_previewed():
    """All-skipped results mean no real execution happened — status is 'previewed'."""
    results = [{"status": "skipped"}, {"status": "skipped"}]
    assert determine_final_status(results) == "previewed"


def test_determine_final_status_normal_execution_returns_executed():
    """Successful, non-skipped results return 'executed'."""
    results = [{"status": "ok"}, {"status": "ok"}]
    assert determine_final_status(results) == "executed"


def test_determine_final_status_any_failed_returns_error():
    """Any failed action results in 'error'."""
    results = [{"status": "ok"}, {"status": "failed"}]
    assert determine_final_status(results) == "error"


def test_determine_final_status_meeting_conflict_in_result_data():
    """'conflict' keyword in calendar result data signals a scheduling conflict."""
    results = [
        {
            "action_type": "create_meeting",
            "status": "ok",
            "result": {"error": "Time conflict with existing event"},
        }
    ]
    assert determine_final_status(results) == "conflict"


def test_determine_final_status_meeting_blocked_status():
    """Calendar action with 'blocked' status signals a scheduling conflict."""
    results = [{"action_type": "create_meeting", "status": "blocked", "result": {}}]
    assert determine_final_status(results) == "conflict"
