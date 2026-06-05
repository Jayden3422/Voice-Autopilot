"""Calendar payload helpers: title enrichment, preview prep, finalization, confirmation."""

import html
from datetime import datetime, timedelta


def resolve_date(value: str, ref_dt, lang: str = "en") -> str:
    """Ensure a date value is in YYYY-MM-DD format."""
    if not value:
        return ref_dt.strftime("%Y-%m-%d")
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return value
    except ValueError:
        pass
    try:
        import dateparser
        dt = dateparser.parse(value, settings={
            "PREFER_DATES_FROM": "future",
            "RELATIVE_BASE": ref_dt.replace(tzinfo=None),
        })
        if dt:
            return dt.strftime("%Y-%m-%d")
    except Exception:
        pass
    return value


def resolve_time(value: str) -> str:
    """Ensure a time value is in HH:MM 24-hour format."""
    if not value:
        return ""
    try:
        datetime.strptime(value, "%H:%M")
        return value
    except ValueError:
        pass
    try:
        return datetime.strptime(value, "%H:%M:%S").strftime("%H:%M")
    except ValueError:
        pass
    for fmt in ("%I:%M %p", "%I:%M%p", "%I %p", "%I%p"):
        try:
            return datetime.strptime(value.strip(), fmt).strftime("%H:%M")
        except ValueError:
            continue
    return value


def enrich_calendar_title(payload: dict, summary: str, extracted: dict, lang: str) -> dict:
    """Enrich calendar title with key business information (budget, product, company)."""
    current_title = payload.get("title", "")
    if not current_title or len(current_title) < 10:
        current_title = summary[:60] if summary else ("Meeting" if lang == "en" else "会议")

    info_parts = []
    entities = extracted.get("entities") or {}
    company = entities.get("company")
    if company:
        info_parts.append(company)

    products = extracted.get("product_interest", [])
    if products:
        info_parts.append(", ".join(products[:2]))

    budget = extracted.get("budget")
    if budget and isinstance(budget, dict):
        currency = budget.get("currency", "CAD")
        range_min = budget.get("range_min")
        range_max = budget.get("range_max")
        if range_min is not None or range_max is not None:
            if range_min == range_max and range_min is not None:
                budget_str = f"{currency} ${range_min:,.0f}"
            elif range_min is not None and range_max is not None:
                budget_str = f"{currency} ${range_min:,.0f}-${range_max:,.0f}"
            elif range_min is not None:
                budget_str = f"{currency} ${range_min:,.0f}+"
            else:
                budget_str = f"{currency} <${range_max:,.0f}"
            info_parts.append(budget_str)

    if info_parts:
        enriched = current_title
        for part in info_parts:
            if part and part.lower() not in enriched.lower():
                enriched = f"{enriched} - {part}"
        payload["title"] = enriched[:117] + "..." if len(enriched) > 120 else enriched
    elif not payload.get("title"):
        payload["title"] = summary[:80] if summary else ("Meeting" if lang == "en" else "会议")

    return payload


def prepare_calendar_payload_for_preview(payload: dict, summary: str, lang: str, current_dt) -> dict:
    """Ensure calendar payload has editable fields without forcing defaults or LLM calls."""
    if not payload.get("title"):
        payload["title"] = summary[:80] if summary else ("Meeting" if lang == "en" else "日程安排")
    if "date" not in payload:
        payload["date"] = ""
    if payload.get("date"):
        payload["date"] = resolve_date(payload["date"], current_dt, lang)
    if "start_time" not in payload:
        payload["start_time"] = ""
    if payload.get("start_time"):
        payload["start_time"] = resolve_time(payload["start_time"])
    if "end_time" not in payload:
        if payload.get("start_time"):
            try:
                st = datetime.strptime(payload["start_time"], "%H:%M")
                payload["end_time"] = (st + timedelta(hours=1)).strftime("%H:%M")
            except Exception:
                payload["end_time"] = ""
        else:
            payload["end_time"] = ""
    elif payload.get("end_time"):
        payload["end_time"] = resolve_time(payload["end_time"])
    if "attendees" not in payload:
        payload["attendees"] = []
    return payload


def finalize_calendar_payload(payload: dict, summary: str, lang: str, current_dt) -> dict:
    """Fill missing fields with defaults right before execution."""
    if not payload.get("title"):
        payload["title"] = summary[:80] if summary else ("Meeting" if lang == "en" else "日程安排")
    if payload.get("date"):
        payload["date"] = resolve_date(payload["date"], current_dt, lang)
    else:
        payload["date"] = (current_dt + timedelta(days=1)).strftime("%Y-%m-%d")
    if payload.get("start_time"):
        payload["start_time"] = resolve_time(payload["start_time"])
    else:
        payload["start_time"] = "10:00"
    if payload.get("end_time"):
        payload["end_time"] = resolve_time(payload["end_time"])
    else:
        try:
            st = datetime.strptime(payload["start_time"], "%H:%M")
            payload["end_time"] = (st + timedelta(hours=1)).strftime("%H:%M")
        except Exception:
            payload["end_time"] = "11:00"
    if "attendees" not in payload:
        payload["attendees"] = []
    return payload


def build_calendar_confirmation(payload: dict, lang: str = "en") -> dict:
    title = payload.get("title", "Meeting" if lang == "en" else "日程安排")
    date = payload.get("date", "")
    start = payload.get("start_time", "")
    end = payload.get("end_time", "")
    if lang.startswith("zh"):
        text = f"日历已创建：{title}，{date} {start}-{end}。"
    else:
        text = f"Calendar confirmed: {title} on {date} {start}-{end}."
    return {"text": text, "html": f"<p><strong>{html.escape(text)}</strong></p>"}
