"""Tests for actions/calendar.py — pure calendar helpers."""

import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from actions.calendar import (
    build_calendar_confirmation,
    enrich_calendar_title,
    finalize_calendar_payload,
    prepare_calendar_payload_for_preview,
    resolve_date,
    resolve_time,
)

REF = datetime(2026, 6, 10, 9, 0)  # Tuesday 09:00


# ── resolve_date ──────────────────────────────────────────────────────────────

def test_resolve_date_already_formatted():
    """ISO date in YYYY-MM-DD passes through unchanged."""
    assert resolve_date("2026-08-20", REF) == "2026-08-20"


def test_resolve_date_empty_returns_ref():
    """Empty string returns reference date as YYYY-MM-DD."""
    assert resolve_date("", REF) == "2026-06-10"


def test_resolve_date_none_returns_ref():
    """None returns reference date as YYYY-MM-DD."""
    assert resolve_date(None, REF) == "2026-06-10"


# ── resolve_time ──────────────────────────────────────────────────────────────

def test_resolve_time_already_hhmm():
    """HH:MM 24-hour format passes through unchanged."""
    assert resolve_time("14:30") == "14:30"


def test_resolve_time_with_seconds_stripped():
    """HH:MM:SS is truncated to HH:MM."""
    assert resolve_time("09:15:00") == "09:15"


def test_resolve_time_12hr_pm():
    """'3:30 PM' converts to 24-hour '15:30'."""
    assert resolve_time("3:30 PM") == "15:30"


def test_resolve_time_12hr_am():
    """'10:00 AM' converts to '10:00'."""
    assert resolve_time("10:00 AM") == "10:00"


def test_resolve_time_midnight_12hr():
    """'12:00 AM' converts to midnight '00:00'."""
    assert resolve_time("12:00 AM") == "00:00"


def test_resolve_time_noon_12hr():
    """'12:00 PM' converts to noon '12:00'."""
    assert resolve_time("12:00 PM") == "12:00"


def test_resolve_time_empty_passthrough():
    """Empty string returns empty string."""
    assert resolve_time("") == ""


# ── enrich_calendar_title ─────────────────────────────────────────────────────

def test_enrich_calendar_title_appends_company():
    """Company name is appended to the title when not already present."""
    payload = {"title": "Follow-up call"}
    extracted = {"entities": {"company": "Acme Corp"}, "product_interest": [], "budget": None}
    result = enrich_calendar_title(payload, "Follow-up call", extracted, "en")
    assert "Acme Corp" in result["title"]


def test_enrich_calendar_title_short_title_replaced_when_info_parts_present():
    """Short title is swapped for the summary when business info is also being appended."""
    payload = {"title": "Hi"}
    extracted = {"entities": {"company": "Acme Corp"}, "product_interest": [], "budget": None}
    result = enrich_calendar_title(payload, "Important product demo with enterprise client", extracted, "en")
    assert result["title"].startswith("Important product demo")
    assert "Acme Corp" in result["title"]


def test_enrich_calendar_title_no_duplicate_company():
    """Company already present in the title is not appended a second time."""
    payload = {"title": "Acme Corp Review"}
    extracted = {"entities": {"company": "Acme Corp"}, "product_interest": [], "budget": None}
    result = enrich_calendar_title(payload, "Review", extracted, "en")
    assert result["title"].count("Acme Corp") == 1


def test_enrich_calendar_title_with_budget_range():
    """Budget range is appended to the title."""
    payload = {"title": "Sales call"}
    extracted = {
        "entities": {},
        "product_interest": [],
        "budget": {"currency": "CAD", "range_min": 50000, "range_max": 100000},
    }
    result = enrich_calendar_title(payload, "Sales call", extracted, "en")
    assert "CAD" in result["title"]
    assert "50,000" in result["title"]


def test_enrich_calendar_title_capped_at_120_chars():
    """Title exceeding 120 characters is truncated with ellipsis."""
    payload = {"title": "X"}
    extracted = {"entities": {"company": "B" * 100}, "product_interest": [], "budget": None}
    result = enrich_calendar_title(payload, "A" * 200, extracted, "en")
    assert len(result["title"]) <= 120


def test_enrich_calendar_title_default_zh_when_empty():
    """Empty title with no summary defaults to Chinese '会议' in zh mode."""
    payload = {}
    extracted = {"entities": {}, "product_interest": [], "budget": None}
    result = enrich_calendar_title(payload, "", extracted, "zh")
    assert result["title"] == "会议"


# ── prepare_calendar_payload_for_preview ─────────────────────────────────────

def test_prepare_payload_initialises_missing_fields_to_empty():
    """Missing date/time fields are set to empty strings, not defaults."""
    result = prepare_calendar_payload_for_preview({}, "Meeting", "en", REF)
    assert result["date"] == ""
    assert result["start_time"] == ""
    assert result["end_time"] == ""
    assert result["attendees"] == []


def test_prepare_payload_infers_end_time_plus_one_hour():
    """end_time is set to start_time + 1 hour when start_time is present."""
    payload = {"start_time": "09:00"}
    result = prepare_calendar_payload_for_preview(payload, "", "en", REF)
    assert result["end_time"] == "10:00"


def test_prepare_payload_normalises_12hr_times():
    """12-hour time strings are converted to 24-hour."""
    payload = {"start_time": "2:00 PM", "end_time": "3:00 PM"}
    result = prepare_calendar_payload_for_preview(payload, "", "en", REF)
    assert result["start_time"] == "14:00"
    assert result["end_time"] == "15:00"


def test_prepare_payload_fills_title_from_summary_when_absent():
    """Missing title is filled from the summary."""
    result = prepare_calendar_payload_for_preview({}, "Project kickoff", "en", REF)
    assert result["title"] == "Project kickoff"


# ── finalize_calendar_payload ─────────────────────────────────────────────────

def test_finalize_missing_date_defaults_to_tomorrow():
    """Missing date defaults to tomorrow relative to the reference datetime."""
    result = finalize_calendar_payload({}, "Meeting", "en", REF)
    assert result["date"] == "2026-06-11"


def test_finalize_missing_start_time_defaults_to_10am():
    """Missing start_time defaults to '10:00'."""
    result = finalize_calendar_payload({}, "Meeting", "en", REF)
    assert result["start_time"] == "10:00"


def test_finalize_infers_end_time_from_start():
    """end_time is inferred as start_time + 1 hour when missing."""
    result = finalize_calendar_payload({"start_time": "14:00"}, "Meeting", "en", REF)
    assert result["end_time"] == "15:00"


def test_finalize_preserves_all_provided_values():
    """Explicitly provided fields are not overwritten by defaults."""
    payload = {
        "date": "2026-07-01",
        "start_time": "11:00",
        "end_time": "12:30",
        "title": "Custom title",
    }
    result = finalize_calendar_payload(payload, "Ignored summary", "en", REF)
    assert result["date"] == "2026-07-01"
    assert result["start_time"] == "11:00"
    assert result["end_time"] == "12:30"
    assert result["title"] == "Custom title"


# ── build_calendar_confirmation ───────────────────────────────────────────────

def test_build_confirmation_english_contains_event_details():
    """English confirmation text includes title, date, and time range."""
    payload = {
        "title": "Team Standup",
        "date": "2026-06-15",
        "start_time": "10:00",
        "end_time": "10:30",
    }
    result = build_calendar_confirmation(payload, "en")
    assert "Team Standup" in result["text"]
    assert "2026-06-15" in result["text"]
    assert "10:00" in result["text"]


def test_build_confirmation_english_returns_html():
    """English confirmation returns a non-empty HTML string."""
    payload = {"title": "Demo", "date": "2026-06-15", "start_time": "14:00", "end_time": "15:00"}
    result = build_calendar_confirmation(payload, "en")
    assert "<p>" in result["html"]


def test_build_confirmation_chinese_contains_event_details():
    """Chinese confirmation text includes the title and Chinese label."""
    payload = {
        "title": "团队站会",
        "date": "2026-06-15",
        "start_time": "10:00",
        "end_time": "10:30",
    }
    result = build_calendar_confirmation(payload, "zh")
    assert "团队站会" in result["text"]
    assert "日历已创建" in result["text"]
