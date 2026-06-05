"""Settings REST API — CRUD for connector/calendar config + Google OAuth2 flow."""

import copy
import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, RedirectResponse

import store.settings_store as ss
from store.settings_deps import get_settings_store

router = APIRouter(prefix="/settings", tags=["settings"])
logger = logging.getLogger(__name__)

# Fields that must never be echoed back in plaintext
_SENSITIVE = {"smtp_pass", "api_key", "access_token", "refresh_token", "client_secret", "webhook_url"}


def _mask(settings: dict) -> dict:
    """Return a deep copy with sensitive non-empty fields replaced by '***'."""
    masked = copy.deepcopy(settings)

    def _walk(d: dict) -> None:
        for k, v in d.items():
            if isinstance(v, dict):
                _walk(v)
            elif k in _SENSITIVE and v:
                d[k] = "***"

    _walk(masked)
    return masked


def _merge_preserving_masked(current: dict, new: dict) -> None:
    """Merge *new* into *current* in-place, keeping existing values for '***' fields."""
    for k, v in new.items():
        if isinstance(current.get(k), dict) and isinstance(v, dict):
            _merge_preserving_masked(current[k], v)
        elif k in _SENSITIVE and v == "***":
            pass  # keep existing secret
        else:
            current[k] = v


@router.get("")
async def get_settings(
    settings: Annotated[dict, Depends(get_settings_store)],
):
    return _mask(settings)


@router.put("")
async def update_settings(body: dict):
    current = ss.load()
    _merge_preserving_masked(current, body)
    ss.save(current)
    return {"status": "ok"}


# ── Google Calendar OAuth2 ────────────────────────────────────────────────────

@router.get("/google-calendar/auth-url")
async def get_auth_url():
    config = ss.get_google_api_config()
    client_id = config.get("client_id", "")
    client_secret = config.get("client_secret", "")
    redirect_uri = config.get("redirect_uri", "http://localhost:8888/settings/google-calendar/callback")

    if not client_id or not client_secret:
        return JSONResponse(
            status_code=400,
            content={"error": "Google API client_id and client_secret must be saved in Settings first"},
        )

    try:
        from google_auth_oauthlib.flow import Flow

        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [redirect_uri],
                }
            },
            scopes=["https://www.googleapis.com/auth/calendar"],
        )
        flow.redirect_uri = redirect_uri
        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )
        return {"auth_url": auth_url}
    except ImportError:
        return JSONResponse(
            status_code=500,
            content={"error": "google-auth-oauthlib not installed. Run: pip install google-auth-oauthlib"},
        )
    except Exception as e:
        logger.exception("Failed to generate OAuth2 auth URL")
        return JSONResponse(status_code=500, content={"error": str(e)[:300]})


@router.get("/google-calendar/callback")
async def google_callback(code: str = "", error: str = ""):
    """Handle the OAuth2 redirect from Google and store the tokens."""
    frontend_settings = "http://localhost:5173/settings"

    if error:
        return RedirectResponse(url=f"{frontend_settings}?gc_error={error}")
    if not code:
        return RedirectResponse(url=f"{frontend_settings}?gc_error=no_code")

    config = ss.get_google_api_config()
    client_id = config.get("client_id", "")
    client_secret = config.get("client_secret", "")
    redirect_uri = config.get("redirect_uri", "http://localhost:8888/settings/google-calendar/callback")

    try:
        from google_auth_oauthlib.flow import Flow

        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [redirect_uri],
                }
            },
            scopes=["https://www.googleapis.com/auth/calendar"],
        )
        flow.redirect_uri = redirect_uri
        flow.fetch_token(code=code)
        creds = flow.credentials

        ss.update_google_tokens(
            access_token=creds.token,
            refresh_token=creds.refresh_token,
            token_expiry=creds.expiry.isoformat() if creds.expiry else None,
        )
        return RedirectResponse(url=f"{frontend_settings}?gc_connected=1")
    except Exception as e:
        logger.exception("OAuth2 callback error")
        import urllib.parse
        return RedirectResponse(url=f"{frontend_settings}?gc_error={urllib.parse.quote(str(e)[:100])}")


@router.get("/google-calendar/status")
async def google_calendar_status():
    config = ss.get_google_api_config()
    return {
        "has_credentials": bool(config.get("client_id") and config.get("client_secret")),
        "is_connected": bool(config.get("refresh_token") or config.get("access_token")),
        "calendar_id": config.get("calendar_id", "primary"),
    }


@router.post("/google-calendar/disconnect")
async def disconnect_google():
    ss.clear_google_tokens()
    return {"status": "ok"}
