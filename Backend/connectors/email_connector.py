"""Email connector via SMTP."""

import html
import logging
import os
import smtplib
import socket
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import store.settings_store as ss

logger = logging.getLogger(__name__)


async def dry_run(payload: dict) -> dict:
    """Return a preview of the email without sending."""
    to = payload.get("to", "")
    subject = payload.get("subject", "")
    body = payload.get("body_text") or payload.get("body", "")
    return {
        "preview": f"Email → {to}\nSubject: {subject}\nBody: {body[:200]}{'…' if len(body) > 200 else ''}",
        "to": to,
        "subject": subject,
    }


async def execute(payload: dict) -> dict:
    """Send an email via SMTP."""
    cfg = ss.get_connector("email")
    host = cfg.get("smtp_host", "") or os.getenv("SMTP_HOST", "")
    port = int(cfg.get("smtp_port") or os.getenv("SMTP_PORT", "587"))
    user = cfg.get("smtp_user", "") or os.getenv("SMTP_USER", "")
    password = cfg.get("smtp_pass", "") or os.getenv("SMTP_PASS", "")
    from_addr = cfg.get("smtp_from", "") or os.getenv("SMTP_FROM", user)
    timeout = float(cfg.get("smtp_timeout") or os.getenv("SMTP_TIMEOUT", "20"))
    use_ssl = bool(cfg.get("smtp_ssl")) or os.getenv("SMTP_SSL", "").lower() in ("1", "true", "yes") or port == 465

    if not host or not user:
        return {"status": "failed", "error": "SMTP not configured (SMTP_HOST, SMTP_USER required)"}

    to = payload.get("to", "")
    subject = payload.get("subject", "")
    body_text = payload.get("body_text") or payload.get("body", "")
    body_html = payload.get("body_html", "")

    if not to:
        return {"status": "failed", "error": "Recipient email (to) is required"}

    msg = MIMEMultipart("alternative")
    _cfg = ss.get_connector("email")
    _default_from_name = _cfg.get("smtp_from_name", "") or os.getenv("SMTP_FROM_NAME", "")
    from_name = payload.get("from_name") or _default_from_name
    if from_name:
        msg["From"] = f"{from_name} <{from_addr}>"
    else:
        msg["From"] = from_addr
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body_text or "", "plain", "utf-8"))
    if body_html:
        msg.attach(MIMEText(body_html, "html", "utf-8"))

    try:
        if use_ssl:
            server = smtplib.SMTP_SSL(host, port, timeout=timeout)
        else:
            server = smtplib.SMTP(host, port, timeout=timeout)
        with server:
            server.ehlo()
            if not use_ssl and port != 25:
                server.starttls()
                server.ehlo()
            if password:
                server.login(user, password)
            server.sendmail(from_addr, [to], msg.as_string())
        logger.info("Email sent to %s: %s", to, subject)
        return {"status": "success", "summary": f"Email sent to {to}: {subject}"}
    except socket.timeout:
        logger.exception("SMTP timeout")
        return {"status": "failed", "error": "SMTP timeout. Check SMTP_HOST/PORT or network connectivity."}
    except smtplib.SMTPException as e:
        logger.exception("SMTP error")
        return {"status": "failed", "error": f"SMTP error: {str(e)[:300]}"}
    except Exception as e:
        logger.exception("Email send error")
        return {"status": "failed", "error": str(e)[:300]}


# ── Email content builder ────────────────────────────────────────────────────


def _starts_with_greeting(text: str, lang: str) -> bool:
    s = (text or "").strip().lower()
    if not s:
        return False
    if lang == "zh":
        return s.startswith(("你好", "您好", "嗨", "哈喽"))
    return s.startswith(("hi", "hello", "dear"))


def _text_to_html(text: str) -> str:
    if not text:
        return ""
    paragraphs = []
    for block in text.strip().split("\n\n"):
        lines = [html.escape(line) for line in block.split("\n")]
        paragraphs.append("<p>" + "<br/>".join(lines) + "</p>")
    return "\n".join(paragraphs)


def build_email_content(draft: dict, extracted: dict) -> dict:
    """Build structured email content (subject, body_text, body_html, to, from) from draft and extracted data."""
    from utils.lang import normalize_lang

    lang = normalize_lang(extracted.get("conversation_language", "en"))
    entities = extracted.get("entities") or {}
    to_addr = entities.get("email") or ""
    contact = entities.get("contact_name") or ""

    reply_text = (draft or {}).get("reply_text", "").strip()
    summary = extracted.get("summary", "")
    subject_prefix = "Re: " if lang == "en" else "回复: "
    subject = f"{subject_prefix}{summary[:60]}" if summary else ("Follow-up" if lang == "en" else "跟进")

    greeting = ""
    if not _starts_with_greeting(reply_text, lang):
        if lang == "zh":
            greeting = f"您好{contact}：" if contact else "您好："
        else:
            greeting = f"Hi {contact}," if contact else "Hello,"

    signature = "Voice Autopilot (noreply)" if lang == "en" else "Voice Autopilot（noreply）"
    footer = (
        "This is an automated message from noreply. Please do not reply."
        if lang == "en"
        else "此邮件由 noreply 自动发送，请勿直接回复。"
    )

    body_parts = []
    if greeting:
        body_parts.append(greeting)
    if reply_text:
        body_parts.append(reply_text)
    body_parts.append(signature)
    body_parts.append(footer)
    body_text = "\n\n".join(body_parts).strip()

    body_html = "\n".join(filter(None, [
        f"<p>{html.escape(greeting)}</p>" if greeting else "",
        _text_to_html(reply_text),
        f"<p><strong>{html.escape(signature)}</strong></p>",
        f"<p class=\"email-footer\">{html.escape(footer)}</p>",
    ]))

    from_addr = os.getenv("SMTP_FROM") or os.getenv("SMTP_USER") or "noreply@example.com"
    from_name = os.getenv("SMTP_FROM_NAME", "Voice Autopilot")
    if "noreply" not in (from_name or "").lower():
        from_name = f"{from_name} (noreply)"
    from_display = f"{from_name} <{from_addr}>"

    return {
        "subject": subject,
        "body_text": body_text,
        "body_html": body_html,
        "to": to_addr,
        "from_display": from_display,
        "from_name": from_name,
    }
