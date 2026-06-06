"""FastAPI routes for the Autopilot system."""

import asyncio
import logging
import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from openai import AsyncOpenAI

from ai_client import get_openai_client
from actions.calendar import enrich_calendar_title, finalize_calendar_payload, build_calendar_confirmation
from actions.dispatcher import dry_run_action, execute_action
from actions.enrichment import (
    build_rag_query,
    enrich_actions,
    append_confirmation_to_slack_payload,
    append_confirmation_to_email_payload,
    merge_extracted_actions,
    determine_final_status,
)
from extraction.autopilot_extractor import extract_autopilot_json
from extraction.calendar_extractor import extract_calendar_event
from extraction.reply_drafter import generate_reply_draft
from connectors.email_connector import build_email_content
from rag.retrieve import retrieve
from resources.base import ResourceFailed
from store.runs import create_run, update_run, get_run, list_runs
from api.models import AutopilotRunRequest, AutopilotConfirmRequest, AutopilotAdjustRequest
from speech.speech import transcribe_audio_base64
from utils.lang import normalize_lang
from utils.timezone import now as now_toronto

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/autopilot", tags=["autopilot"])


# --- POST /autopilot/run ---

@router.post("/run")
async def autopilot_run(
    req: AutopilotRunRequest,
    client: Annotated[AsyncOpenAI, Depends(get_openai_client)],
):
    run_id = str(uuid.uuid4())

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

    create_run(run_id, req.mode, raw_input or "", run_type="autopilot")

    try:
        # Step 1: Transcription
        if req.mode == "audio":
            transcript = await transcribe_audio_base64(req.audio_base64, lang=normalize_lang(req.locale))
        else:
            transcript = req.text.strip()

        if not transcript:
            raise HTTPException(status_code=400, detail="Empty transcript")

        update_run(run_id, transcript=transcript, status="transcribed")

        # Step 2: Extraction via Tool Calling
        extracted = await extract_autopilot_json(transcript, client=client, run_id=run_id)
        update_run(run_id, extracted_json=extracted, status="extracted")

        # Step 3: RAG retrieval
        evidence = await retrieve(build_rag_query(extracted), client)
        update_run(run_id, evidence_json=evidence)

        # Step 4: Reply draft
        draft = await generate_reply_draft(client, transcript, extracted, evidence, run_id=run_id)

        entities = extracted.get("entities") or {}
        email_content = build_email_content(draft, extracted) if entities.get("email") else None

        reply_payload = {
            "text": draft.get("reply_text", ""),
            "reply_text": draft.get("reply_text", ""),
            "citations": draft.get("citations", []),
            "html": email_content.get("body_html", "") if email_content else "",
            "subject": email_content.get("subject", "") if email_content else "",
            "to": email_content.get("to", "") if email_content else "",
            "from": email_content.get("from_display", "") if email_content else "",
            "body_text": email_content.get("body_text", "") if email_content else "",
        }
        update_run(run_id, reply_draft=reply_payload, status="drafted")

        # Step 5: Enrich & dry_run preview (parallelized)
        actions = extracted.get("next_best_actions", [])
        actions = await enrich_actions(actions, extracted, draft, email_content, transcript)

        previews = await asyncio.gather(*[dry_run_action(a) for a in actions])
        actions_preview = [
            {**action, "preview": preview.get("preview", "")}
            for action, preview in zip(actions, previews)
        ]
        update_run(run_id, actions_json=actions_preview, status="previewed")

        return {
            "run_id": run_id,
            "transcript": transcript,
            "extracted": merge_extracted_actions(extracted, actions),
            "evidence": evidence,
            "reply_draft": reply_payload,
            "actions_preview": actions_preview,
        }

    except (HTTPException, ResourceFailed):
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

    actions = list(req.actions or [])
    extracted_json = run.get("extracted_json", {}) if isinstance(run.get("extracted_json"), dict) else {}
    locale = extracted_json.get("conversation_language", "en") if isinstance(extracted_json, dict) else "en"
    summary = extracted_json.get("summary", "") if isinstance(extracted_json, dict) else ""
    current_dt = now_toronto()

    # Classify each action as executable or not
    action_meta = []
    for idx, action in enumerate(actions):
        action_type = action.get("action_type", "none")
        skip = action.get("skip", False)
        requires_confirm = action.get("requires_confirmation", True)
        confirmed = action.get("confirmed", False)
        if skip or action_type == "none":
            action_meta.append({"idx": idx, "action": action, "exec": False, "reason": ""})
        elif requires_confirm and not confirmed:
            action_meta.append({"idx": idx, "action": action, "exec": False, "reason": "Not confirmed"})
        else:
            action_meta.append({"idx": idx, "action": action, "exec": True, "reason": ""})

    calendar_indices = [m["idx"] for m in action_meta if m["exec"] and m["action"].get("action_type") == "create_meeting"]
    results_by_index: dict[int, dict] = {}
    calendar_success = True
    confirmation_text = ""
    confirmation_html = ""

    if calendar_indices:
        for idx in calendar_indices:
            action = actions[idx]
            try:
                payload = action.get("payload") or {}
                payload = enrich_calendar_title(payload, summary, extracted_json, locale)
                payload = finalize_calendar_payload(payload, summary, locale, current_dt)
                action["payload"] = payload
                result = await execute_action(action, lang=locale)
                results_by_index[idx] = result
                if result.get("status") != "success":
                    calendar_success = False
                    break
                if not confirmation_text:
                    confirm = build_calendar_confirmation(action.get("payload", {}), locale)
                    confirmation_text = confirm.get("text", "")
                    confirmation_html = confirm.get("html", "")
            except Exception as e:
                logger.exception("Action execution error for create_meeting")
                results_by_index[idx] = {"action_type": "create_meeting", "status": "failed", "result": {"error": str(e)[:300]}}
                calendar_success = False
                break

        if not calendar_success:
            for m in action_meta:
                idx = m["idx"]
                if idx in results_by_index:
                    continue
                reason = m["reason"] if not m["exec"] else "Calendar not created yet"
                results_by_index[idx] = {
                    "action_type": actions[idx].get("action_type", "none"),
                    "status": "skipped",
                    "result": {"reason": reason} if reason else {},
                }

    if not calendar_indices or calendar_success:
        for m in action_meta:
            idx = m["idx"]
            action = m["action"]
            action_type = action.get("action_type", "none")
            if idx in results_by_index:
                continue
            if not m["exec"]:
                reason = m["reason"]
                results_by_index[idx] = {
                    "action_type": action_type,
                    "status": "skipped",
                    "result": {"reason": reason} if reason else {},
                }
                continue

            if confirmation_text and action_type == "send_slack_summary":
                payload = {**(action.get("payload") or {})}
                append_confirmation_to_slack_payload(payload, confirmation_text)
                action = {**action, "payload": payload}
            if confirmation_text and action_type == "send_email_followup":
                payload = {**(action.get("payload") or {})}
                append_confirmation_to_email_payload(payload, confirmation_text, confirmation_html)
                action = {**action, "payload": payload}

            try:
                result = await execute_action(action, lang=locale)
                results_by_index[idx] = result
            except Exception as e:
                logger.exception("Action execution error for %s", action_type)
                results_by_index[idx] = {"action_type": action_type, "status": "failed", "result": {"error": str(e)[:300]}}

    results = [
        results_by_index.get(i, {"action_type": actions[i].get("action_type", "none"), "status": "skipped", "result": {}})
        for i in range(len(actions))
    ]
    final_status = determine_final_status(results)
    update_run(req.run_id, actions_json=results, status=final_status)

    return {"run_id": req.run_id, "results": results}


# --- POST /autopilot/adjust-time ---

@router.post("/adjust-time")
async def autopilot_adjust_time(
    req: AutopilotAdjustRequest,
    client: Annotated[AsyncOpenAI, Depends(get_openai_client)],
):
    action = req.action or {}
    if action.get("action_type") != "create_meeting":
        raise HTTPException(status_code=400, detail="Only create_meeting can be adjusted")

    locale = normalize_lang(req.locale)

    if req.mode == "audio":
        if not req.audio_base64:
            raise HTTPException(status_code=400, detail="audio_base64 is required for audio mode")
        user_text = await transcribe_audio_base64(req.audio_base64, lang=locale)
    elif req.mode == "text":
        if not req.text:
            raise HTTPException(status_code=400, detail="text is required for text mode")
        user_text = req.text.strip()
    else:
        raise HTTPException(status_code=400, detail="mode must be 'audio' or 'text'")

    if not user_text:
        raise HTTPException(status_code=400, detail="Empty transcript")

    payload = action.get("payload") or {}
    context_event = {
        "date": payload.get("date", ""),
        "start_time": payload.get("start_time", ""),
        "end_time": payload.get("end_time", ""),
        "title": payload.get("title", "Meeting" if locale == "en" else "日程安排"),
        "attendees": payload.get("attendees", []),
    }

    extracted = await extract_calendar_event(user_text, client=client, lang=locale, context_event=context_event)

    payload.update({
        "date": extracted.get("date", payload.get("date")),
        "start_time": extracted.get("start_time", payload.get("start_time")),
        "end_time": extracted.get("end_time", payload.get("end_time")),
        "title": extracted.get("title", payload.get("title")),
    })
    if "attendees" in extracted:
        payload["attendees"] = extracted.get("attendees", payload.get("attendees", []))

    updated_action = {**action, "payload": payload}
    preview = await dry_run_action(updated_action)
    updated_action["preview"] = preview.get("preview", "")

    return {"action": updated_action, "user_text": user_text}


# --- POST /autopilot/ingest ---

@router.post("/ingest")
async def autopilot_ingest(
    client: Annotated[AsyncOpenAI, Depends(get_openai_client)],
):
    """Re-ingest the knowledge base into the FAISS index."""
    from rag.ingest import ingest_knowledge_base
    from rag.ingest_lock import IngestInProgress

    try:
        result = await ingest_knowledge_base(client)
    except IngestInProgress as exc:
        raise HTTPException(
            status_code=409,
            detail={"error": "ingest_in_progress"},
        ) from exc
    return {"status": "ok", **result}


# --- GET /autopilot/runs ---

@router.get("/runs")
async def get_autopilot_runs(limit: int = 50, offset: int = 0, run_type: Optional[str] = None):
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 100")
    if offset < 0:
        raise HTTPException(status_code=400, detail="offset must be non-negative")
    if run_type and run_type not in ("autopilot", "voice_schedule"):
        raise HTTPException(status_code=400, detail="run_type must be 'autopilot' or 'voice_schedule'")
    runs = list_runs(limit=limit, offset=offset, run_type=run_type)
    return {"runs": runs, "limit": limit, "offset": offset, "run_type": run_type}


# --- GET /autopilot/runs/{run_id} ---

@router.get("/runs/{run_id}")
async def get_autopilot_run_detail(run_id: str):
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return run


# --- POST /autopilot/retry/{run_id} ---

@router.post("/retry/{run_id}")
async def autopilot_retry(run_id: str):
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    previous_actions = run.get("actions_json", [])
    if not previous_actions or not isinstance(previous_actions, list):
        raise HTTPException(status_code=400, detail="No actions found to retry")

    extracted_json = run.get("extracted_json", {})
    if not isinstance(extracted_json, dict):
        extracted_json = {}

    locale = extracted_json.get("conversation_language", "en")
    summary = extracted_json.get("summary", "")
    current_dt = now_toronto()

    actions_to_retry = [
        (idx, {
            "action_type": action.get("action_type"),
            "payload": action.get("payload", {}),
            "requires_confirmation": False,
            "confirmed": True,
        })
        for idx, action in enumerate(previous_actions)
        if action.get("status") in ("failed", "blocked", "error")
    ]

    if not actions_to_retry:
        raise HTTPException(status_code=400, detail="No failed actions to retry")

    results = list(previous_actions)
    for idx, action in actions_to_retry:
        action_type = action.get("action_type", "none")
        try:
            if action_type == "create_meeting":
                payload = action.get("payload") or {}
                payload = enrich_calendar_title(payload, summary, extracted_json, locale)
                payload = finalize_calendar_payload(payload, summary, locale, current_dt)
                action["payload"] = payload
            result = await execute_action(action, lang=locale)
            results[idx] = result
        except Exception as e:
            logger.exception("Retry action execution error for %s", action_type)
            results[idx] = {"action_type": action_type, "status": "failed", "result": {"error": str(e)[:300]}}

    final_status = determine_final_status(results)
    update_run(run_id, actions_json=results, status=final_status)

    return {"run_id": run_id, "results": results, "status": final_status}
