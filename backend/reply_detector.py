"""
Email reply detector — scans Gmail inbox for replies to application emails.
Uses Gmail IMAP (with SMTP_EMAIL/SMTP_PASSWORD credentials).
Marks applications as 'response_received' when reply detected.
Triggers Telegram alert + stage move suggestion.
"""
import email
import imaplib
import logging
import re
from datetime import datetime, timedelta

from config import PROFILE, SMTP_EMAIL, SMTP_PASSWORD

logger = logging.getLogger(__name__)


def check_for_replies(dry_run: bool = False) -> dict:
    """
    Connect to Gmail IMAP, check for new replies to applications.
    Returns stats: {checked, replies_found, updated_apps}
    """
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        return {"error": "SMTP credentials not configured", "checked": 0}

    from database import Application, ApplicationLog, Job, SessionLocal

    stats = {"checked": 0, "replies_found": 0, "updated_apps": 0, "errors": 0}
    db = SessionLocal()
    try:
        # Get applications waiting for response
        apps = (
            db.query(Application)
            .filter(
                Application.email_sent == True,
                Application.response_received == False,
                Application.hr_email != None,
            )
            .all()
        )

        if not apps:
            return {**stats, "message": "No pending applications to check"}

        try:
            mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
            mail.login(SMTP_EMAIL, SMTP_PASSWORD)
            mail.select("INBOX")
        except Exception as e:
            logger.error(f"IMAP login failed: {e}")
            return {**stats, "error": f"IMAP login failed: {e}"}

        # Check for emails from each HR address
        for app in apps:
            stats["checked"] += 1
            hr_email = app.hr_email
            if not hr_email or "@" not in hr_email:
                continue
            try:
                # Search for emails FROM this hr_email after the application date
                since_date = (app.email_sent_at or datetime.utcnow() - timedelta(days=90)).strftime("%d-%b-%Y")
                status, msg_ids = mail.search(None, f'(FROM "{hr_email}" SINCE "{since_date}")')
                if status != "OK":
                    continue
                ids = msg_ids[0].split()
                if not ids:
                    continue

                stats["replies_found"] += 1
                # Read the latest reply for context
                latest_id = ids[-1]
                status, msg_data = mail.fetch(latest_id, "(RFC822)")
                if status != "OK":
                    continue

                raw = msg_data[0][1]
                email_msg = email.message_from_bytes(raw)
                subject = email_msg.get("Subject", "")

                # Classify the reply intent
                intent = _classify_reply_intent(subject, _get_body(email_msg))

                if dry_run:
                    logger.info(f"[DRY RUN] Would update app {app.id}: reply from {hr_email}, intent={intent}")
                    continue

                # Update application
                app.response_received = True
                app.response_date = datetime.utcnow()
                if intent == "interview":
                    app.stage = "phone_screen"
                elif intent == "rejection":
                    app.stage = "rejected"

                db.add(ApplicationLog(
                    job_id=app.job_id,
                    action=f"reply_received_{intent}",
                    detail=f"From {hr_email}: {subject[:100]}",
                ))
                db.commit()
                stats["updated_apps"] += 1

                # Telegram alert
                try:
                    from telegram_notifier import send as tg_send
                    job = db.query(Job).filter(Job.id == app.job_id).first()
                    if job:
                        emoji = {"interview": "🎉", "rejection": "😔", "neutral": "📬"}[intent]
                        tg_send(
                            f"{emoji} <b>Reply received from {job.company}!</b>\n"
                            f"Role: {job.title}\n"
                            f"Intent: {intent}\n"
                            f"Subject: {subject[:80]}"
                        )
                except Exception:
                    pass

                logger.info(f"Reply detected: {hr_email} → app {app.id} (intent={intent})")

            except Exception as e:
                logger.warning(f"Error checking app {app.id}: {e}")
                stats["errors"] += 1
                continue

        mail.logout()
    finally:
        db.close()

    return stats


def _get_body(msg) -> str:
    """Extract plain text body from email message."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                try:
                    return part.get_payload(decode=True).decode("utf-8", errors="ignore")
                except Exception:
                    continue
    else:
        try:
            return msg.get_payload(decode=True).decode("utf-8", errors="ignore")
        except Exception:
            return ""
    return ""


def _classify_reply_intent(subject: str, body: str) -> str:
    """Heuristic-classify reply as interview/rejection/neutral."""
    combined = (subject + " " + body).lower()
    if re.search(r'\b(interview|schedule|chat|call|meet|availability|when (are you|can you)|next step|move forward|technical screen|phone screen)\b', combined):
        return "interview"
    if re.search(r'\b(unfortunately|not (a |moving )|other candidates|position has been filled|not be (moving|proceeding)|regret|decided not to|not selected|reject)\b', combined):
        return "rejection"
    return "neutral"
