"""
Thank-you email after interview.
Auto-triggered when application stage changes to 'interview'.
Sent the same day within 24 hours via Gemini-generated personalized message.
"""
import logging
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import PROFILE, SMTP_EMAIL, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT
from database import Application, ApplicationLog, Job, SessionLocal

logger = logging.getLogger(__name__)


def send_thankyou(application_id: int, dry_run: bool = False) -> bool:
    """Send a thank-you email for an interview. Call after stage moves to 'interview'."""
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        logger.warning("SMTP not configured — skipping thank-you email")
        return False

    db = SessionLocal()
    try:
        app = db.query(Application).filter(Application.id == application_id).first()
        if not app or not app.hr_email:
            return False
        job = db.query(Job).filter(Job.id == app.job_id).first()
        if not job:
            return False

        body = _generate_body(job)
        subject = f"Thank you — {job.title} Interview at {job.company}"

        if not dry_run:
            success = _send(app.hr_email, subject, body)
            if success:
                db.add(ApplicationLog(
                    job_id=job.id,
                    action="thankyou_sent",
                    detail=f"to={app.hr_email}",
                ))
                db.commit()
            return success
        else:
            logger.info(f"[DRY RUN] Thank-you → {app.hr_email} | {job.title}")
            return True
    finally:
        db.close()


def _generate_body(job: Job) -> str:
    try:
        from gemini import _run, PROFILE_SUMMARY
        prompt = f"""Write a brief, professional thank-you email after an interview.
Candidate: {PROFILE.get('name')} interviewed for {job.title} at {job.company}
Context: {PROFILE_SUMMARY[:200]}

Rules:
- 2-3 short paragraphs
- Thank for the time and opportunity
- Reiterate specific enthusiasm for the role/company
- Express readiness to provide anything needed
- Professional and warm, not sycophantic
- Return ONLY the email body (no subject line, no salutation)"""
        result = _run(prompt, timeout=30)
        if result and len(result) > 50:
            p = PROFILE
            return (
                f"Dear Hiring Manager,\n\n"
                f"{result}\n\n"
                f"Best regards,\n"
                f"{p.get('name','')}\n"
                f"{p.get('phone','')}\n"
                f"{p.get('email','')}\n"
                f"LinkedIn: {p.get('linkedin','')}"
            )
    except Exception:
        pass

    # Fallback
    p = PROFILE
    return (
        f"Dear Hiring Manager,\n\n"
        f"Thank you for taking the time to interview me for the {job.title} position at {job.company}. "
        f"It was a pleasure learning more about the role and the team.\n\n"
        f"I remain very excited about this opportunity and am confident my experience in mobile "
        f"development would enable me to contribute effectively. Please let me know if you need "
        f"any additional information.\n\n"
        f"I look forward to hearing from you.\n\n"
        f"Best regards,\n"
        f"{p.get('name','')}\n"
        f"{p.get('phone','')}\n"
        f"{p.get('email','')}\n"
        f"LinkedIn: {p.get('linkedin','')}"
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
        logger.info(f"Thank-you email sent → {to}")
        return True
    except Exception as e:
        logger.error(f"Thank-you email failed → {to}: {e}")
        return False
