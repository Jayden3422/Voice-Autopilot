"""Action enrichment and orchestration helpers."""

import json
import logging

from actions.calendar import enrich_calendar_title, prepare_calendar_payload_for_preview

logger = logging.getLogger(__name__)


def build_rag_query(extracted: dict) -> str:
    """Build a FAISS search query from extracted fields."""
    parts = []
    intent = extracted.get("intent", "")
    if intent:
        parts.append(intent.replace("_", " "))
    products = extracted.get("product_interest", [])
    if products:
        parts.append(" ".join(products))
    summary = extracted.get("summary", "")
    if summary:
        parts.append(summary)
    return " ".join(parts) if parts else "general inquiry"


async def enrich_actions(
    actions: list[dict],
    extracted: dict,
    draft: dict,
    email_content: dict | None = None,
    transcript: str = "",
) -> list[dict]:
    """Post-process actions: fill missing payload fields, drop actions with no viable data."""
    from utils.timezone import now as now_toronto

    current_dt = now_toronto()
    summary = extracted.get("summary", "")
    intent = extracted.get("intent", "")
    urgency = extracted.get("urgency", "")
    entities = extracted.get("entities") or {}
    email = entities.get("email")
    email_content = email_content or {}
    contact = entities.get("contact_name", "")
    company = entities.get("company", "")
    lang = extracted.get("conversation_language", "en")

    slack_msg_parts = []
    if intent:
        slack_msg_parts.append(f"Intent: {intent.replace('_', ' ')}")
    if urgency:
        slack_msg_parts.append(f"Urgency: {urgency}")
    if company:
        slack_msg_parts.append(f"Company: {company}")
    if contact:
        slack_msg_parts.append(f"Contact: {contact}")
    if summary:
        slack_msg_parts.append(f"Summary: {summary}")
    slack_msg = "\n".join(slack_msg_parts) if slack_msg_parts else summary
    if not slack_msg:
        slack_msg = "Autopilot summary unavailable." if lang == "en" else "Autopilot 摘要暂无。"

    action_list = list(actions or [])
    if not any(a.get("action_type") == "send_slack_summary" for a in action_list):
        action_list.append({
            "action_type": "send_slack_summary",
            "requires_confirmation": True,
            "confidence": 0.9,
            "payload": {},
        })
    if email and not any(a.get("action_type") == "send_email_followup" for a in action_list):
        action_list.append({
            "action_type": "send_email_followup",
            "requires_confirmation": True,
            "confidence": 0.9,
            "payload": {},
        })

    enriched = []
    for action in action_list:
        a = {**action}
        payload = {**(a.get("payload") or {})}
        atype = a.get("action_type", "none")

        if atype == "create_meeting":
            payload = enrich_calendar_title(payload, summary, extracted, lang)
            payload = prepare_calendar_payload_for_preview(payload, summary, lang, current_dt)

        elif atype == "send_slack_summary":
            if not payload.get("message"):
                payload["message"] = slack_msg
            if not payload.get("channel"):
                payload["channel"] = "#general"

        elif atype == "send_email_followup":
            if not payload.get("to"):
                if email:
                    payload["to"] = email
                else:
                    continue
            if not payload.get("subject"):
                subject = email_content.get("subject", "")
                if not subject:
                    subject_prefix = "Re: " if lang == "en" else "回复: "
                    subject = f"{subject_prefix}{summary[:60]}" if summary else ("Follow-up" if lang == "en" else "跟进")
                payload["subject"] = subject
            body_text = email_content.get("body_text") or payload.get("body_text") or payload.get("body") or ""
            if not body_text:
                reply_text = draft.get("reply_text", "") if draft else ""
                body_text = reply_text if reply_text else summary
            payload["body_text"] = body_text
            payload["body"] = body_text
            body_html = email_content.get("body_html") or payload.get("body_html") or ""
            if body_html:
                payload["body_html"] = body_html
            from_name = email_content.get("from_name")
            if from_name:
                payload["from_name"] = from_name

        elif atype == "create_ticket":
            if not payload.get("title"):
                payload["title"] = summary[:120] if summary else "New ticket"
            if not payload.get("description"):
                payload["description"] = summary
            if not payload.get("priority"):
                priority_map = {"high": "high", "medium": "medium", "low": "low"}
                payload["priority"] = priority_map.get(urgency, "medium")

        a["payload"] = payload
        enriched.append(a)

    return enriched


def append_confirmation_to_slack_payload(payload: dict, confirmation_text: str) -> None:
    msg = (payload.get("message") or "").strip()
    payload["message"] = f"{msg}\n\n{confirmation_text}" if msg else confirmation_text


def append_confirmation_to_email_payload(
    payload: dict, confirmation_text: str, confirmation_html: str
) -> None:
    body_text = (payload.get("body_text") or payload.get("body") or "").strip()
    payload["body_text"] = f"{body_text}\n\n{confirmation_text}" if body_text else confirmation_text
    payload["body"] = payload["body_text"]
    body_html = (payload.get("body_html") or "").strip()
    payload["body_html"] = f"{body_html}\n{confirmation_html}" if body_html else confirmation_html


def merge_extracted_actions(extracted: dict, enriched_actions: list[dict]) -> dict:
    """Merge enriched action payloads back into extracted output for display."""
    try:
        merged = json.loads(json.dumps(extracted))
    except Exception:
        merged = dict(extracted or {})
    pool = list(enriched_actions or [])
    for ex in merged.get("next_best_actions", []) or []:
        atype = ex.get("action_type")
        match_idx = next((i for i, a in enumerate(pool) if a.get("action_type") == atype), None)
        if match_idx is None:
            continue
        ex["payload"] = pool.pop(match_idx).get("payload") or ex.get("payload") or {}
    return merged


def determine_final_status(results: list[dict]) -> str:
    """Determine final run status from action execution results."""
    if not any(r.get("status") not in ("skipped",) for r in results):
        return "previewed"

    for result in results:
        if result.get("action_type") == "create_meeting":
            status = result.get("status", "")
            result_data = result.get("result", {})
            if status == "blocked" or "conflict" in str(result_data).lower():
                return "conflict"
            if status == "failed":
                error_msg = str(result_data.get("error", "")).lower()
                if "conflict" in error_msg or "already" in error_msg:
                    return "conflict"

    if any(r.get("status") == "failed" for r in results):
        return "error"

    return "executed"
