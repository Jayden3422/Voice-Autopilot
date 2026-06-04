"""Google Calendar API connector (OAuth2 + Calendar API v3).

Requires:
    pip install google-api-python-client google-auth-oauthlib google-auth-httplib2
"""

import asyncio
import logging
import os

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _build_service(config: dict):
    """Build an authorized Google Calendar API service, refreshing tokens if needed."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    import store.settings_store as ss

    creds = Credentials(
        token=config.get("access_token"),
        refresh_token=config.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=config.get("client_id"),
        client_secret=config.get("client_secret"),
        scopes=SCOPES,
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        ss.update_google_tokens(
            access_token=creds.token,
            refresh_token=creds.refresh_token,
            token_expiry=creds.expiry.isoformat() if creds.expiry else None,
        )

    return build("calendar", "v3", credentials=creds)


def _tz():
    try:
        import zoneinfo
        return zoneinfo.ZoneInfo(os.getenv("TIMEZONE", "America/Toronto"))
    except Exception:
        from datetime import timezone
        return timezone.utc


def _to_rfc3339(date: str, time_str: str) -> str:
    from datetime import datetime
    dt = datetime.strptime(f"{date}T{time_str}:00", "%Y-%m-%dT%H:%M:%S")
    return dt.replace(tzinfo=_tz()).isoformat()


def _check_conflict_sync(service, calendar_id: str, date: str, start_time: str, end_time: str) -> bool:
    start_rfc = _to_rfc3339(date, start_time)
    end_rfc = _to_rfc3339(date, end_time)
    result = (
        service.events()
        .list(
            calendarId=calendar_id,
            timeMin=start_rfc,
            timeMax=end_rfc,
            singleEvents=True,
        )
        .execute()
    )
    return len(result.get("items", [])) > 0


def _create_event_sync(
    service, calendar_id: str, date: str, start_time: str, end_time: str, title: str, attendees: list
) -> dict:
    tz_name = os.getenv("TIMEZONE", "America/Toronto")
    event = {
        "summary": title,
        "start": {"dateTime": f"{date}T{start_time}:00", "timeZone": tz_name},
        "end": {"dateTime": f"{date}T{end_time}:00", "timeZone": tz_name},
    }
    if attendees:
        event["attendees"] = [{"email": a} for a in attendees if "@" in str(a)]
    return service.events().insert(calendarId=calendar_id, body=event).execute()


async def dry_run(payload: dict) -> dict:
    """Preview without hitting the API (identical shape to Playwright preview)."""
    title = payload.get("title", "Untitled")
    d = payload.get("date", "TBD")
    start = payload.get("start_time", "TBD")
    end = payload.get("end_time", "TBD")
    attendees = payload.get("attendees", [])
    att_str = ", ".join(attendees) if attendees else "none"
    return {
        "preview": f"[API] Calendar: {title} on {d} from {start} to {end} (attendees: {att_str})",
        "title": title,
        "date": d,
        "mode": "api",
    }


async def execute(payload: dict) -> dict:
    """Create a Google Calendar event via the API."""
    try:
        import store.settings_store as ss

        config = ss.get_google_api_config()

        if not config.get("client_id") or not config.get("client_secret"):
            return {
                "action_type": "create_meeting",
                "status": "failed",
                "result": {"error": "Google Calendar API not configured — missing client_id or client_secret"},
            }

        if not config.get("refresh_token") and not config.get("access_token"):
            return {
                "action_type": "create_meeting",
                "status": "failed",
                "result": {"error": "Google Calendar not authorized. Please connect in Settings."},
            }

        d = payload.get("date")
        start = payload.get("start_time")
        end = payload.get("end_time")
        title = payload.get("title", "Meeting")
        attendees = payload.get("attendees", [])
        calendar_id = config.get("calendar_id", "primary")

        def _run():
            service = _build_service(config)
            if _check_conflict_sync(service, calendar_id, d, start, end):
                return {"conflict": True}
            created = _create_event_sync(service, calendar_id, d, start, end, title, attendees)
            return {"conflict": False, "event": created}

        result = await asyncio.to_thread(_run)

        if result.get("conflict"):
            return {
                "action_type": "create_meeting",
                "status": "blocked",
                "result": {
                    "conflict": True,
                    "message": f"Time slot {d} {start}–{end} is already booked.",
                    "suggestion": "Reply with a new time and I'll reschedule it.",
                },
            }

        event = result.get("event", {})
        return {
            "action_type": "create_meeting",
            "status": "success",
            "result": {
                "message": f"Created: {title} on {d} {start}–{end}",
                "summary": f"Created: {title} on {d} {start}–{end}",
                "link": event.get("htmlLink", ""),
            },
        }

    except Exception as e:
        logger.exception("Google Calendar API execution error")
        return {
            "action_type": "create_meeting",
            "status": "failed",
            "result": {"error": str(e)[:300]},
        }
