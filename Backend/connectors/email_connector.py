"""Email connector via SMTP."""

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


async def dry_run(payload: dict) -> dict:
    """Return a preview of the email without sending."""
    to = payload.get("to", "")
    subject = payload.get("subject", "")
    body = payload.get("body", "")
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

    if not host or not user:
        return {"status": "failed", "error": "SMTP not configured (SMTP_HOST, SMTP_USER required)"}

    to = payload.get("to", "")
    subject = payload.get("subject", "")
    body = payload.get("body", "")

    if not to:
        return {"status": "failed", "error": "Recipient email (to) is required"}

    msg = MIMEMultipart()
    msg["From"] = from_addr
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        with smtplib.SMTP(host, port, timeout=15) as server:
            server.ehlo()
            if port != 25:
                server.starttls()
                server.ehlo()
            if password:
                server.login(user, password)
            server.sendmail(from_addr, [to], msg.as_string())
        logger.info("Email sent to %s: %s", to, subject)
        return {"status": "success", "summary": f"Email sent to {to}: {subject}"}
    except smtplib.SMTPException as e:
        logger.exception("SMTP error")
        return {"status": "failed", "error": f"SMTP error: {str(e)[:300]}"}
    except Exception as e:
        logger.exception("Email send error")
        return {"status": "failed", "error": str(e)[:300]}
