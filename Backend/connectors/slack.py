"""Slack connector via Incoming Webhook."""

import json
import logging
import os

import httpx

logger = logging.getLogger(__name__)

WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
TIMEOUT = 15


async def dry_run(payload: dict) -> dict:
    """Return a preview of the Slack message without sending."""
    channel = payload.get("channel", "#general")
    message = payload.get("message", "")
    return {
        "preview": f"Slack → {channel}: {message[:200]}{'…' if len(message) > 200 else ''}",
        "channel": channel,
        "message_length": len(message),
    }


async def execute(payload: dict) -> dict:
    """Send a message to Slack via webhook."""
    url = WEBHOOK_URL
    if not url:
        return {"status": "failed", "error": "SLACK_WEBHOOK_URL not configured"}

    message = payload.get("message", "")
    if not message:
        return {"status": "failed", "error": "Empty message"}

    body = {"text": message}
    channel = payload.get("channel")
    if channel:
        body["channel"] = channel

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(url, json=body)
            if resp.status_code == 200 and resp.text == "ok":
                logger.info("Slack message sent successfully")
                return {"status": "success", "summary": f"Message sent to Slack ({len(message)} chars)"}
            else:
                logger.error("Slack webhook returned %s: %s", resp.status_code, resp.text[:200])
                return {"status": "failed", "error": f"Slack returned {resp.status_code}: {resp.text[:200]}"}
    except httpx.TimeoutException:
        return {"status": "failed", "error": "Slack webhook timed out"}
    except Exception as e:
        logger.exception("Slack send error")
        return {"status": "failed", "error": str(e)[:300]}
