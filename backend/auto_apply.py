"""
Auto-apply engine — generates cover letters via Gemini, finds HR emails,
sends applications via Gmail SMTP.

EMAIL RULE: Only the PDF resume is sent. Resume text/content NEVER appears
in the email body. Body = cover letter + signature only.
"""
import logging
import os
import smtplib
from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import (AUTO_APPLY_ENABLED, AUTO_APPLY_MIN_SCORE,
                    LINKEDIN_EMAIL, PROFILE,
                    SMTP_EMAIL, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT)
from contact_finder import find_contact
from database import AIAnalysis, Application, ApplicationLog, Job, ResumeProfile, SessionLocal
from gemini import generate_cover_letter, select_best_resume

logger = logging.getLogger(__name__)

_DEFAULT_RESUME_PDF = os.getenv(
    "DEFAULT_RESUME_PDF",
    os.path.join(os.path.dirname(__file__), "..", "data", "resumes", "default.pdf"),
)


def _pick_resume_pdf(job: Job, db) -> str:
    """
    Uses Gemini to pick the best resume for this job.
    Returns ONLY the PDF file path — resume text is never passed to emails.
    """
    resumes = db.query(ResumeProfile).all()
    if not resumes:
        return _DEFAULT_RESUME_PDF

    resume_dicts = [
        {
            "id": r.id,
            "name": r.name,
            "content": r.content or "",
            "target_roles": r.target_roles or "[]",
            "description": r.description or "",
        }
        for r in resumes
    ]
    chosen = select_best_resume(job.title, job.description or "", resume_dicts)
    if not chosen:
        fallback = next((r for r in resumes if r.is_default), resumes[0])
        pdf = fallback.pdf_path
    else:
        r_obj = next((r for r in resumes if r.id == chosen["id"]), resumes[0])
        pdf = r_obj.pdf_path

    # Verify PDF exists; fall back to default if not
    if pdf and os.path.exists(pdf):
        return pdf
    if os.path.exists(_DEFAULT_RESUME_PDF):
        return _DEFAULT_RESUME_PDF
    return ""


def run_auto_apply(dry_run: bool = False) -> dict:
    """Find eligible jobs and send applications. Returns {attempted, sent, skipped, errors}."""
    if not AUTO_APPLY_ENABLED and not dry_run:
        logger.info("Auto-apply disabled. Set AUTO_APPLY_ENABLED=true in .env.")
        return {"attempted": 0, "sent": 0, "skipped": 0, "errors": 0, "disabled": True}

    if not SMTP_EMAIL or not SMTP_PASSWORD:
        logger.error("SMTP_EMAIL and SMTP_PASSWORD required in .env")
        return {"attempted": 0, "sent": 0, "skipped": 0, "errors": 1}

    db = SessionLocal()
    stats = {"attempted": 0, "sent": 0, "skipped": 0, "errors": 0}
    try:
        jobs = (
            db.query(Job)
            .filter(
                Job.status == "new",
                Job.match_score >= AUTO_APPLY_MIN_SCORE,
                Job.auto_applied == False,
            )
            .order_by(Job.match_score.desc())
            .limit(10)
            .all()
        )
        logger.info(f"Auto-apply: {len(jobs)} eligible jobs (min score {AUTO_APPLY_MIN_SCORE})")
        for job in jobs:
            stats["attempted"] += 1
            try:
                result = _apply_to_job(job, db, dry_run)
                if result == "sent":
                    stats["sent"] += 1
                elif result == "skipped":
                    stats["skipped"] += 1
                else:
                    stats["errors"] += 1
            except Exception as e:
                logger.error(f"Auto-apply error job {job.id}: {e}")
                stats["errors"] += 1
    finally:
        db.close()

    logger.info(f"Auto-apply complete: {stats}")
    return stats


def _apply_to_job(job: Job, db, dry_run: bool) -> str:
    """Apply to one job. Returns 'sent', 'skipped', or 'error'."""
    existing = db.query(Application).filter_by(job_id=job.id).first()
    if existing and existing.email_sent:
        job.auto_applied = True
        db.commit()
        return "skipped"

    analysis = db.query(AIAnalysis).filter_by(job_id=job.id).first()
    if analysis and not analysis.apply_recommended:
        logger.info(f"Skipping job {job.id} — Gemini recommends no")
        return "skipped"

    # Pick best PDF resume (text never touches email)
    resume_pdf = _pick_resume_pdf(job, db)
    if not resume_pdf:
        logger.warning(f"No resume PDF found — skipping job {job.id}")
        return "skipped"

    hr_email = find_contact(job.company, job.url or "", job.description or "")
    if not hr_email:
        logger.warning(f"No HR email for {job.company} (job {job.id})")
        return "skipped"

    # Cover letter (AI-generated, cached)
    if analysis and analysis.cover_letter:
        cover_letter = analysis.cover_letter
    else:
        cover_letter = generate_cover_letter(job.title, job.company, job.description or "")
        if not cover_letter:
            logger.warning(f"Gemini cover letter failed for job {job.id}")
            return "error"
        if analysis:
            analysis.cover_letter = cover_letter
        else:
            analysis = AIAnalysis(job_id=job.id, cover_letter=cover_letter, apply_recommended=True)
            db.add(analysis)

    subject = f"Application for {job.title} — {PROFILE.get('name', '')}"
    # Strip A/B variant tag before sending
    try:
        from cover_letter_ab import strip_tag
        outgoing_cl = strip_tag(cover_letter)
    except Exception:
        outgoing_cl = cover_letter
    # Email body: cover letter + signature ONLY. No resume text. PDF attached separately.
    body = _build_email_body(job, outgoing_cl)

    if not dry_run:
        if not _send_email(hr_email, subject, body, resume_pdf):
            return "error"
    else:
        logger.info(f"[DRY RUN] → {hr_email} | {job.title} @ {job.company} | pdf={resume_pdf}")

    if not existing:
        db.add(Application(
            job_id=job.id, hr_email=hr_email, cover_letter=cover_letter,
            email_sent=not dry_run,
            email_sent_at=datetime.utcnow() if not dry_run else None,
            stage="applied",
        ))
    else:
        existing.hr_email = hr_email
        existing.cover_letter = cover_letter
        existing.email_sent = not dry_run
        existing.email_sent_at = datetime.utcnow() if not dry_run else None

    job.status = "applied" if not dry_run else job.status
    job.auto_applied = not dry_run
    job.applied_date = datetime.utcnow() if not dry_run else job.applied_date

    db.add(ApplicationLog(
        job_id=job.id,
        action="email_sent" if not dry_run else "dry_run_apply",
        detail=f"to={hr_email} pdf={os.path.basename(resume_pdf)} dry_run={dry_run}",
    ))
    db.commit()

    # LinkedIn message after email
    if not dry_run and LINKEDIN_EMAIL:
        try:
            from linkedin_messenger import find_recruiter_and_message, generate_linkedin_message
            msg = generate_linkedin_message(job.title, job.company, cover_letter[:100])
            find_recruiter_and_message(job.company, job.title, job.id, msg, dry_run=False)
            db.add(ApplicationLog(job_id=job.id, action="linkedin_message_queued",
                                  detail=f"company={job.company}"))
            db.commit()
        except Exception as e:
            logger.warning(f"LinkedIn message failed job {job.id}: {e}")

    return "sent"


def _build_email_body(job: Job, cover_letter: str) -> str:
    """
    Email body = cover letter + signature only.
    Resume text is NEVER included — only the PDF is attached.
    """
    p = PROFILE
    return (
        f"Dear Hiring Manager,\n\n"
        f"{cover_letter}\n\n"
        f"Please find my resume attached.\n\n"
        f"Best regards,\n"
        f"{p.get('name', '')}\n"
        f"{p.get('phone', '')}\n"
        f"{p.get('email', '')}\n"
        f"LinkedIn: {p.get('linkedin', '')}\n"
        f"GitHub: {p.get('github', '')}"
    )


def _send_email(to_email: str, subject: str, body: str, resume_pdf: str) -> bool:
    """
    Sends email with:
    - Body: cover letter + signature (plain text)
    - Attachment: PDF resume ONLY — no resume text in body
    """
    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = SMTP_EMAIL
    msg["To"] = to_email
    msg["Reply-To"] = PROFILE.get("email", SMTP_EMAIL)
    msg.attach(MIMEText(body, "plain"))

    # PDF attachment only — never inline resume text
    if resume_pdf and os.path.exists(resume_pdf):
        with open(resume_pdf, "rb") as f:
            pdf = MIMEApplication(f.read(), _subtype="pdf")
            pdf.add_header(
                "Content-Disposition", "attachment",
                filename=f"{PROFILE.get('name', 'Resume').replace(' ', '_')}_Resume.pdf",
            )
            msg.attach(pdf)
        logger.info(f"Attaching PDF: {os.path.basename(resume_pdf)}")
    else:
        logger.warning(f"Resume PDF not found at {resume_pdf} — sending without attachment")

    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as srv:
            srv.login(SMTP_EMAIL, SMTP_PASSWORD)
            srv.sendmail(SMTP_EMAIL, to_email, msg.as_string())
        logger.info(f"Email sent → {to_email}")
        return True
    except Exception as e:
        logger.error(f"Email failed → {to_email}: {e}")
        return False
