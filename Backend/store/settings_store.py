"""Settings persistence layer — stores connector and calendar config in settings.json."""

import json
import logging
import os
from copy import deepcopy
from pathlib import Path

logger = logging.getLogger(__name__)

SETTINGS_FILE = Path(__file__).parent.parent / "settings.json"

_DEFAULT: dict = {
    "connectors": {
        "slack": {"enabled": False, "webhook_url": ""},
        "email": {
            "enabled": False,
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
            "smtp_user": "",
            "smtp_pass": "",
            "smtp_from": "",
            "smtp_from_name": "Voice Autopilot",
            "smtp_ssl": False,
            "smtp_timeout": 30,
        },
        "linear": {"enabled": False, "api_key": "", "team_id": ""},
    },
    "calendar": {
        "mode": "playwright",
        "google_api": {
            "client_id": "",
            "client_secret": "",
            "redirect_uri": "http://localhost:8888/settings/google-calendar/callback",
            "access_token": None,
            "refresh_token": None,
            "token_expiry": None,
            "calendar_id": "primary",
        },
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    result = deepcopy(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def _apply_env_defaults(s: dict) -> None:
    """Seed empty fields from environment variables on first load."""
    slack = s["connectors"]["slack"]
    if not slack["webhook_url"]:
        slack["webhook_url"] = os.getenv("SLACK_WEBHOOK_URL", "")
    if slack["webhook_url"]:
        slack["enabled"] = True

    email = s["connectors"]["email"]
    for field, env_key in [
        ("smtp_host", "SMTP_HOST"),
        ("smtp_user", "SMTP_USER"),
        ("smtp_pass", "SMTP_PASS"),
        ("smtp_from", "SMTP_FROM"),
        ("smtp_from_name", "SMTP_FROM_NAME"),
    ]:
        if not email[field]:
            email[field] = os.getenv(env_key, email[field])
    if os.getenv("SMTP_PORT"):
        email["smtp_port"] = int(os.getenv("SMTP_PORT", 587))
    if email["smtp_user"]:
        email["enabled"] = True

    lin = s["connectors"]["linear"]
    if not lin["api_key"]:
        lin["api_key"] = os.getenv("LINEAR_API_KEY", "")
    if not lin["team_id"]:
        lin["team_id"] = os.getenv("LINEAR_TEAM_ID", "")
    if lin["api_key"]:
        lin["enabled"] = True


def load() -> dict:
    """Load settings, merging with defaults to ensure all keys exist."""
    if not SETTINGS_FILE.exists():
        s = deepcopy(_DEFAULT)
        _apply_env_defaults(s)
        return s
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return _deep_merge(_DEFAULT, data)
    except Exception:
        logger.exception("Failed to load settings.json, using defaults")
        return deepcopy(_DEFAULT)


def save(settings: dict) -> None:
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)


# ── Connector helpers ────────────────────────────────────────────────────────

def get_connector(name: str) -> dict:
    """Return connector config with env-var fallback for empty fields."""
    cfg = deepcopy(load()["connectors"].get(name, {}))
    if name == "slack":
        if not cfg.get("webhook_url"):
            cfg["webhook_url"] = os.getenv("SLACK_WEBHOOK_URL", "")
    elif name == "email":
        for field, env_key in [
            ("smtp_host", "SMTP_HOST"),
            ("smtp_user", "SMTP_USER"),
            ("smtp_pass", "SMTP_PASS"),
            ("smtp_from", "SMTP_FROM"),
            ("smtp_from_name", "SMTP_FROM_NAME"),
        ]:
            if not cfg.get(field):
                cfg[field] = os.getenv(env_key, cfg.get(field, ""))
        if not cfg.get("smtp_port"):
            cfg["smtp_port"] = int(os.getenv("SMTP_PORT", 587))
    elif name == "linear":
        if not cfg.get("api_key"):
            cfg["api_key"] = os.getenv("LINEAR_API_KEY", "")
        if not cfg.get("team_id"):
            cfg["team_id"] = os.getenv("LINEAR_TEAM_ID", "")
    return cfg


def is_connector_enabled(name: str) -> bool:
    return bool(get_connector(name).get("enabled", False))


# ── Calendar helpers ─────────────────────────────────────────────────────────

def get_calendar_mode() -> str:
    return load()["calendar"].get("mode", "playwright")


def get_google_api_config() -> dict:
    return deepcopy(load()["calendar"]["google_api"])


def update_google_tokens(access_token: str, refresh_token: str | None, token_expiry: str | None) -> None:
    s = load()
    ga = s["calendar"]["google_api"]
    ga["access_token"] = access_token
    ga["refresh_token"] = refresh_token
    ga["token_expiry"] = token_expiry
    save(s)


def clear_google_tokens() -> None:
    s = load()
    ga = s["calendar"]["google_api"]
    ga["access_token"] = None
    ga["refresh_token"] = None
    ga["token_expiry"] = None
    save(s)
