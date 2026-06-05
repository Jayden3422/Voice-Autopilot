"""Tests for api/settings.py — _mask and _merge_preserving_masked helpers."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.settings import _mask, _merge_preserving_masked


# ── _mask ─────────────────────────────────────────────────────────────────────

def test_mask_replaces_webhook_url():
    """webhook_url is masked in the returned object."""
    settings = {"connectors": {"slack": {"enabled": True, "webhook_url": "https://hooks.slack.com/abc"}}}
    masked = _mask(settings)
    assert masked["connectors"]["slack"]["webhook_url"] == "***"


def test_mask_replaces_smtp_pass():
    """smtp_pass is masked while other email fields remain visible."""
    settings = {"connectors": {"email": {"smtp_pass": "secret123", "smtp_user": "user@gmail.com"}}}
    masked = _mask(settings)
    assert masked["connectors"]["email"]["smtp_pass"] == "***"
    assert masked["connectors"]["email"]["smtp_user"] == "user@gmail.com"


def test_mask_replaces_api_key_but_not_team_id():
    """api_key is masked; non-sensitive team_id is left unchanged."""
    settings = {"connectors": {"linear": {"api_key": "lin_api_123", "team_id": "TEAM1"}}}
    masked = _mask(settings)
    assert masked["connectors"]["linear"]["api_key"] == "***"
    assert masked["connectors"]["linear"]["team_id"] == "TEAM1"


def test_mask_replaces_access_token():
    """access_token is masked while client_id is left visible."""
    settings = {"calendar": {"google_api": {"access_token": "ya29.xyz", "client_id": "client123"}}}
    masked = _mask(settings)
    assert masked["calendar"]["google_api"]["access_token"] == "***"
    assert masked["calendar"]["google_api"]["client_id"] == "client123"


def test_mask_leaves_empty_values_unchanged():
    """Empty strings signal 'not configured' and must not be masked."""
    settings = {"connectors": {"slack": {"webhook_url": ""}}}
    masked = _mask(settings)
    assert masked["connectors"]["slack"]["webhook_url"] == ""


def test_mask_does_not_mutate_original():
    """_mask returns a deep copy — the caller's dict is unchanged."""
    settings = {"connectors": {"slack": {"webhook_url": "https://real"}}}
    _mask(settings)
    assert settings["connectors"]["slack"]["webhook_url"] == "https://real"


# ── _merge_preserving_masked ──────────────────────────────────────────────────

def test_merge_updates_non_sensitive_field():
    """Non-sensitive fields from the new payload overwrite current values."""
    current = {"connectors": {"slack": {"enabled": False, "webhook_url": "https://real"}}}
    _merge_preserving_masked(current, {"connectors": {"slack": {"enabled": True}}})
    assert current["connectors"]["slack"]["enabled"] is True


def test_merge_does_not_destroy_existing_secret_when_incoming_is_masked():
    """Incoming '***' preserves the existing real secret — it is not overwritten."""
    current = {"connectors": {"slack": {"webhook_url": "https://real", "enabled": True}}}
    _merge_preserving_masked(current, {"connectors": {"slack": {"webhook_url": "***"}}})
    assert current["connectors"]["slack"]["webhook_url"] == "https://real"


def test_merge_overwrites_secret_when_new_real_value_provided():
    """A real new value for a sensitive field replaces the old one."""
    current = {"connectors": {"slack": {"webhook_url": "https://old"}}}
    _merge_preserving_masked(current, {"connectors": {"slack": {"webhook_url": "https://new"}}})
    assert current["connectors"]["slack"]["webhook_url"] == "https://new"


def test_merge_preserves_sibling_keys_not_in_payload():
    """Keys present in current but absent from the new payload are left untouched."""
    current = {"connectors": {"email": {"smtp_user": "u@x.com", "smtp_pass": "secret"}}}
    _merge_preserving_masked(current, {"connectors": {"email": {"smtp_user": "new@x.com"}}})
    assert current["connectors"]["email"]["smtp_pass"] == "secret"
    assert current["connectors"]["email"]["smtp_user"] == "new@x.com"
