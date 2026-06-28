"""
Follow-up email engine.
Sends polite follow-up emails 7 days after application with no response.
Tracks follow-up count (max 2 follow-ups per application).
"""
import logging
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import PROFILE, SMTP_EMAIL, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT
from database import Application, ApplicationLog, Job, SessionLocal

logger = logging.getLogger(__name__)

_FOLLOWUP_WAIT_DAYS = [7, 14]  # Day 7 and day 14 follow-ups


def run_followups(dry_run: bool = False) -> dict:
    """Check all applications and send follow-ups where due."""
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        return {"sent": 0, "skipped": 0, "error": "SMTP not configured"}

    db = SessionLocal()
    stats = {"sent": 0, "skipped": 0, "due": 0}
    try:
        apps = (
            db.query(Application)
            .filter(
                Application.email_sent == True,
                Application.response_received == False,
                Application.stage.in_(["applied", "phone_screen"]),
            )
            .all()
        )

        now = datetime.utcnow()
        for app in apps:
            if not app.email_sent_at or not app.hr_email:
                continue

            count = app.follow_up_count or 0
            if count >= 2:
                continue  # max 2 follow-ups

            threshold_days = _FOLLOWUP_WAIT_DAYS[count]
            due_at = app.email_sent_at + timedelta(days=threshold_days)
            if now < due_at:
                continue

            # Check last follow-up was long enough ago
            if app.last_follow_up_at:
                if now < app.last_follow_up_at + timedelta(days=7):
                    continue

            stats["due"] += 1
            job = db.query(Job).filter(Job.id == app.job_id).first()
            if not job:
                continue

            body = _build_followup(job, count + 1)
            subject = f"Re: Application for {job.title} — {PROFILE.get('name', '')}"

            if not dry_run:
                if _send(app.hr_email, subject, body):
                    app.follow_up_count = count + 1
                    app.last_follow_up_at = now
                    db.add(ApplicationLog(
                        job_id=job.id,
                        action=f"follow_up_{count + 1}_sent",
                        detail=f"to={app.hr_email}",
                    ))
                    db.commit()
                    stats["sent"] += 1
                    logger.info(f"Follow-up #{count+1} sent → {app.hr_email} ({job.title})")
                else:
                    stats["skipped"] += 1
            else:
                logger.info(f"[DRY RUN] Follow-up #{count+1} → {app.hr_email} | {job.title}")
                stats["sent"] += 1
    finally:
        db.close()

    return stats


def _build_followup(job: Job, follow_up_num: int) -> str:
    """Generate follow-up email body via Gemini (or fallback template)."""
    try:
        from gemini import _run
        prompt = f"""Write a brief professional follow-up email (2-3 sentences) for:
Candidate: {PROFILE.get('name')} applying for {job.title} at {job.company}
Follow-up number: {follow_up_num} (application sent {'7' if follow_up_num == 1 else '14'} days ago)
Rules: short, polite, reiterate interest, ask about timeline. No resume text. No attachments mentioned.
Return ONLY the email body text."""
        result = _run(prompt, timeout=30)
        if result and len(result) > 30:
            return result
    except Exception:
        pass

    # Fallback template
    p = PROFILE
    if follow_up_num == 1:
        return (
            f"I hope this message finds you well. I wanted to follow up on my application for "
            f"the {job.title} position at {job.company} submitted about a week ago. "
            f"I remain very interested in this opportunity and would love to learn about the next steps.\n\n"
            f"Best regards,\n{p.get('name','')}\n{p.get('phone','')}\n{p.get('email','')}"
        )
    return (
        f"I'm writing once more regarding the {job.title} role at {job.company}. "
        f"I understand you may be busy, but I'd appreciate any update on my candidacy. "
        f"I'm still very keen to contribute to your team.\n\n"
        f"Best regards,\n{p.get('name','')}\n{p.get('phone','')}\n{p.get('email','')}"
    )


def _send(to: str, subject: str, body: str) -> bool:
    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = SMTP_EMAIL
    msg["To"] = to
    msg["Reply-To"] = PROFILE.get("email", SMTP_EMAIL)
    msg.attach(MIMEText(body, "plain"))
    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as srv:
            srv.login(SMTP_EMAIL, SMTP_PASSWORD)
            srv.sendmail(SMTP_EMAIL, to, msg.as_string())
        return True
    except Exception as e:
        logger.error(f"Follow-up send failed → {to}: {e}")
        return False
