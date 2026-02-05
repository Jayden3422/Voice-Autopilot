"""FastAPI routes for the Autopilot system."""

import base64
import json
import logging
import os
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from chat.autopilot_extractor import extract_autopilot_json, get_openai_client
from chat.reply_drafter import generate_reply_draft
from rag.retrieve import retrieve
from actions.dispatcher import dry_run_action, execute_action
from store.runs import create_run, update_run, get_run

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/autopilot", tags=["autopilot"])


# --- Request / Response Models ---

class AutopilotRunRequest(BaseModel):
    mode: str  # "audio" or "text"
    audio_base64: Optional[str] = None
    text: Optional[str] = None
    locale: Optional[str] = "en"


class AutopilotConfirmRequest(BaseModel):
    run_id: str
    actions: list[dict]


# --- POST /autopilot/run ---

@router.post("/run")
async def autopilot_run(req: AutopilotRunRequest):
    run_id = str(uuid.uuid4())

    # Determine input
    if req.mode == "audio":
        if not req.audio_base64:
            raise HTTPException(status_code=400, detail="audio_base64 is required for audio mode")
        raw_input = req.audio_base64[:5000] + "..." if len(req.audio_base64 or "") > 5000 else req.audio_base64
    elif req.mode == "text":
        if not req.text:
            raise HTTPException(status_code=400, detail="text is required for text mode")
        raw_input = req.text
    else:
        raise HTTPException(status_code=400, detail="mode must be 'audio' or 'text'")

    create_run(run_id, req.mode, raw_input or "")

    try:
        # Step 1: Transcription
        transcript = ""
        if req.mode == "audio":
            transcript = await _transcribe_audio(req.audio_base64)
        else:
            transcript = req.text.strip()

        if not transcript:
            raise HTTPException(status_code=400, detail="Empty transcript")

        update_run(run_id, transcript=transcript, status="transcribed")

        # Step 2: Extraction via Tool Calling
        extracted = await extract_autopilot_json(transcript, run_id=run_id)
        update_run(run_id, extracted_json=extracted, status="extracted")

        # Step 3: RAG retrieval
        client = get_openai_client()
        query = _build_rag_query(extracted)
        evidence = await retrieve(query, client)
        update_run(run_id, evidence_json=evidence)

        # Step 4: Reply draft
        draft = await generate_reply_draft(client, transcript, extracted, evidence, run_id=run_id)
        update_run(run_id, reply_draft=draft, status="drafted")

        # Step 5: Enrich & filter actions, then dry_run preview
        actions = extracted.get("next_best_actions", [])
        actions = _enrich_actions(actions, extracted, draft)
        actions_preview = []
        for action in actions:
            preview = await dry_run_action(action)
            actions_preview.append({
                **action,
                "preview": preview.get("preview", ""),
            })
        update_run(run_id, actions_json=actions_preview, status="previewed")

        return {
            "run_id": run_id,
            "transcript": transcript,
            "extracted": extracted,
            "evidence": evidence,
            "reply_draft": {"text": draft.get("reply_text", ""), "citations": draft.get("citations", [])},
            "actions_preview": actions_preview,
        }

    except HTTPException:
        raise
    except ValueError as e:
        update_run(run_id, status="error", error=str(e)[:1000])
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.exception("[%s] Autopilot run error", run_id)
        update_run(run_id, status="error", error=str(e)[:1000])
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)[:200]}")


# --- POST /autopilot/confirm ---

@router.post("/confirm")
async def autopilot_confirm(req: AutopilotConfirmRequest):
    run = get_run(req.run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {req.run_id} not found")

    results = []
    for action in req.actions:
        action_type = action.get("action_type", "none")
        skip = action.get("skip", False)

        if skip or action_type == "none":
            results.append({"action_type": action_type, "status": "skipped", "result": {}})
            continue

        requires_confirm = action.get("requires_confirmation", True)
        if requires_confirm and not action.get("confirmed", False):
            results.append({"action_type": action_type, "status": "skipped", "result": {"reason": "Not confirmed"}})
            continue

        locale = run.get("extracted_json", {}).get("conversation_language", "en") if isinstance(run.get("extracted_json"), dict) else "en"

        try:
            result = await execute_action(action, lang=locale)
            results.append(result)
        except Exception as e:
            logger.exception("Action execution error for %s", action_type)
            results.append({"action_type": action_type, "status": "failed", "result": {"error": str(e)[:300]}})

    update_run(req.run_id, actions_json=results, status="executed")

    return {"run_id": req.run_id, "results": results}


# --- POST /autopilot/ingest ---

@router.post("/ingest")
async def autopilot_ingest():
    """Re-ingest the knowledge base into the FAISS index."""
    from rag.ingest import ingest_knowledge_base
    client = get_openai_client()
    result = await ingest_knowledge_base(client)
    return {"status": "ok", **result}


# --- Helpers ---

async def _transcribe_audio(audio_b64: str) -> str:
    """Decode base64 audio and run Whisper STT."""
    import tempfile
    from tools.speech import transcribe_audio

    audio_bytes = base64.b64decode(audio_b64)
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
        f.write(audio_bytes)
        tmp_path = f.name

    try:
        text = transcribe_audio(tmp_path, lang="en")
        return text.strip()
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


def _enrich_actions(actions: list[dict], extracted: dict, draft: dict) -> list[dict]:
    """
    Post-process actions: fill in missing payload fields from extracted data,
    and drop actions that have no viable data.
    """
    from datetime import datetime, timedelta

    summary = extracted.get("summary", "")
    intent = extracted.get("intent", "")
    urgency = extracted.get("urgency", "")
    entities = extracted.get("entities") or {}
    email = entities.get("email")
    contact = entities.get("contact_name", "")
    company = entities.get("company", "")
    lang = extracted.get("conversation_language", "en")

    # Build a rich Slack message from extracted data
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

    enriched = []
    for action in actions:
        a = {**action}
        payload = {**(a.get("payload") or {})}
        atype = a.get("action_type", "none")

        if atype == "create_meeting":
            # Fill defaults for missing meeting fields
            if not payload.get("title"):
                payload["title"] = summary[:80] if summary else "Meeting"
            if not payload.get("date"):
                # Default to tomorrow
                payload["date"] = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
            if not payload.get("start_time"):
                payload["start_time"] = "10:00"
            if not payload.get("end_time"):
                payload["end_time"] = "11:00"
            if "attendees" not in payload:
                payload["attendees"] = []

        elif atype == "send_slack_summary":
            if not payload.get("message"):
                payload["message"] = slack_msg
            if not payload.get("channel"):
                payload["channel"] = "#general"

        elif atype == "send_email_followup":
            # Only keep if we have a recipient email
            if not payload.get("to"):
                if email:
                    payload["to"] = email
                else:
                    # Skip — no email address available
                    continue
            if not payload.get("subject"):
                subject_prefix = "Re: " if lang == "en" else "回复: "
                payload["subject"] = f"{subject_prefix}{summary[:60]}" if summary else "Follow-up"
            if not payload.get("body"):
                reply_text = draft.get("reply_text", "") if draft else ""
                payload["body"] = reply_text if reply_text else summary

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


def _build_rag_query(extracted: dict) -> str:
    """Build a search query from extracted fields."""
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
