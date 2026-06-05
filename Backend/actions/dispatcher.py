"""Unified action dispatcher: routes actions to connectors for dry_run or execute."""

import asyncio
import logging

from connectors import slack, linear, email_connector

logger = logging.getLogger(__name__)

CONNECTORS = {
    "send_slack_summary": slack,
    "create_ticket": linear,
    "send_email_followup": email_connector,
}


async def dry_run_action(action: dict) -> dict:
    """Generate a preview for a single action without executing."""
    action_type = action.get("action_type", "none")
    payload = action.get("payload", {})

    if action_type == "none":
        return {"preview": "No action needed."}

    if action_type == "create_meeting":
        return _calendar_preview(payload)

    connector = CONNECTORS.get(action_type)
    if connector is None:
        return {"preview": f"Unknown action type: {action_type}"}

    try:
        return await connector.dry_run(payload)
    except Exception as e:
        logger.exception("dry_run failed for %s", action_type)
        return {"preview": f"Preview error: {str(e)[:200]}"}


_CONNECTOR_NAMES = {
    "send_slack_summary": "slack",
    "create_ticket": "linear",
    "send_email_followup": "email",
}


async def execute_action(action: dict, lang: str = "en") -> dict:
    """Execute a single confirmed action."""
    action_type = action.get("action_type", "none")
    payload = action.get("payload", {})

    if action_type == "none":
        return {"action_type": action_type, "status": "skipped", "result": {}}

    if action_type == "create_meeting":
        return await _execute_calendar(payload, lang)

    # Check if connector is enabled in settings
    connector_name = _CONNECTOR_NAMES.get(action_type)
    if connector_name:
        try:
            import store.settings_store as ss
            if not ss.is_connector_enabled(connector_name):
                return {
                    "action_type": action_type,
                    "status": "skipped",
                    "result": {"summary": f"{connector_name.capitalize()} connector is disabled in Settings"},
                }
        except Exception:
            pass  # settings_store unavailable — proceed normally

    connector = CONNECTORS.get(action_type)
    if connector is None:
        return {
            "action_type": action_type,
            "status": "failed",
            "result": {"error": f"Unknown action type: {action_type}"},
        }

    try:
        result = await connector.execute(payload)
        return {"action_type": action_type, "status": result.get("status", "unknown"), "result": result}
    except Exception as e:
        logger.exception("Execute failed for %s", action_type)
        return {"action_type": action_type, "status": "failed", "result": {"error": str(e)[:300]}}


def _calendar_preview(payload: dict) -> dict:
    """Generate a preview string for a calendar event."""
    title = payload.get("title", "Untitled")
    d = payload.get("date", "TBD")
    start = payload.get("start_time", "TBD")
    end = payload.get("end_time", "TBD")
    attendees = payload.get("attendees", [])
    att_str = ", ".join(attendees) if attendees else "none"
    return {
        "preview": f"Calendar: {title} on {d} from {start} to {end} (attendees: {att_str})",
        "title": title,
        "date": d,
    }


async def _execute_calendar(payload: dict, lang: str = "en") -> dict:
    """Execute calendar event creation — Playwright or Google Calendar API based on settings."""
    try:
        import store.settings_store as ss
        mode = ss.get_calendar_mode()
    except Exception:
        mode = "playwright"

    if mode == "api":
        from connectors import google_calendar_api
        return await google_calendar_api.execute(payload)

    # ── Playwright path ────────────────────────────────────────────────────────
    try:
        from datetime import datetime
        from connectors.calendar_agent import GoogleCalendarAgent
        from actions.models import CalendarCommand

        d = payload.get("date")
        start = payload.get("start_time")
        end = payload.get("end_time")
        title = payload.get("title", "Meeting")

        # Parse date
        if isinstance(d, str):
            parsed_date = datetime.strptime(d, "%Y-%m-%d").date()
        else:
            parsed_date = d

        # Parse times
        def _parse_time(t):
            if isinstance(t, str):
                for fmt in ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M%p"):
                    try:
                        return datetime.strptime(t, fmt).time()
                    except ValueError:
                        continue
                raise ValueError(f"Cannot parse time: {t}")
            return t

        parsed_start = _parse_time(start)
        parsed_end = _parse_time(end)

        cmd = CalendarCommand(
            date=parsed_date,
            start_time=parsed_start,
            end_time=parsed_end,
            title=title,
        )

        agent = GoogleCalendarAgent(lang=lang)
        result = await asyncio.to_thread(agent.check_and_create_event, cmd)

        if result.conflict:
            suggestion = (
                "请用语音或文字说出新的时间，我会帮你改期。"
                if lang.startswith("zh")
                else "Reply with a new time (voice or text) and I'll reschedule it."
            )
            return {
                "action_type": "create_meeting",
                "status": "blocked",
                "result": {
                    "conflict": True,
                    "message": result.message,
                    "suggestion": suggestion,
                },
            }
        elif result.success:
            return {
                "action_type": "create_meeting",
                "status": "success",
                "result": {
                    "message": result.message,
                    "summary": f"Created: {title} on {d} {start}-{end}",
                },
            }
        else:
            return {
                "action_type": "create_meeting",
                "status": "failed",
                "result": {"message": result.message},
            }

    except Exception as e:
        logger.exception("Calendar execution error")
        return {
            "action_type": "create_meeting",
            "status": "failed",
            "result": {"error": str(e)[:300]},
        }
