"""Email connector via SMTP."""

import logging
import os
import smtplib
import socket
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

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
    host = os.getenv("SMTP_HOST", "")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "")
    password = os.getenv("SMTP_PASS", "")
    from_addr = os.getenv("SMTP_FROM", user)
    timeout = float(os.getenv("SMTP_TIMEOUT", "20"))
    use_ssl = os.getenv("SMTP_SSL", "").lower() in ("1", "true", "yes") or port == 465

    if not host or not user:
        return {"status": "failed", "error": "SMTP not configured (SMTP_HOST, SMTP_USER required)"}

    to = payload.get("to", "")
    subject = payload.get("subject", "")
    body_text = payload.get("body_text") or payload.get("body", "")
    body_html = payload.get("body_html", "")

    if not to:
        return {"status": "failed", "error": "Recipient email (to) is required"}

    msg = MIMEMultipart("alternative")
    from_name = payload.get("from_name") or os.getenv("SMTP_FROM_NAME", "")
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
