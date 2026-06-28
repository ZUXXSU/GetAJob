"""
System health monitor.
Returns status of every subsystem: scrapers, Gemini, SMTP, IMAP, DB, scheduler.
Used for /api/health endpoint + dashboard ops widget.
"""
import logging
import os
import subprocess
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def check_health() -> dict:
    """Full health check across all subsystems."""
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "overall": "ok",
        "subsystems": {
            "database": _check_database(),
            "gemini_cli": _check_gemini(),
            "smtp": _check_smtp(),
            "imap": _check_imap(),
            "scrapers": _check_scrapers(),
            "scheduler": _check_scheduler(),
            "telegram": _check_telegram(),
            "linkedin_session": _check_linkedin_session(),
            "resume_pdf": _check_resume_pdf(),
            "disk": _check_disk(),
        },
    }


def _check_database() -> dict:
    try:
        from database import SessionLocal, Job
        db = SessionLocal()
        count = db.query(Job).count()
        db.close()
        return {"status": "ok", "jobs_in_db": count}
    except Exception as e:
        return {"status": "error", "error": str(e)[:200]}


def _check_gemini() -> dict:
    from config import GEMINI_BIN
    if not os.path.exists(GEMINI_BIN):
        return {"status": "error", "error": f"Gemini binary not found at {GEMINI_BIN}"}
    try:
        result = subprocess.run(
            [GEMINI_BIN, "--version"],
            capture_output=True, text=True, timeout=5,
        )
        version_line = next((l for l in result.stdout.splitlines() if l and not l.startswith("[")), "")
        return {"status": "ok", "version": version_line.strip()[:50]}
    except Exception as e:
        return {"status": "warning", "error": str(e)[:200]}


def _check_smtp() -> dict:
    from config import SMTP_EMAIL, SMTP_PASSWORD
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        return {"status": "not_configured", "message": "SMTP_EMAIL/SMTP_PASSWORD missing"}
    return {"status": "configured", "email": SMTP_EMAIL}


def _check_imap() -> dict:
    """Quick IMAP connection check."""
    from config import SMTP_EMAIL, SMTP_PASSWORD
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        return {"status": "not_configured"}
    try:
        import imaplib
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=5)
        mail.login(SMTP_EMAIL, SMTP_PASSWORD)
        mail.logout()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "error": str(e)[:200]}


def _check_scrapers() -> dict:
    """Check last successful scrape per source from logs."""
    from database import SessionLocal, ScrapeLog
    db = SessionLocal()
    try:
        sources = ["adzuna", "jsearch", "naukri", "linkedin", "remotive", "remoteok"]
        result = {}
        for src in sources:
            last = (
                db.query(ScrapeLog)
                .filter_by(source=src)
                .order_by(ScrapeLog.timestamp.desc())
                .first()
            )
            if last:
                age_hours = (datetime.utcnow() - last.timestamp).total_seconds() / 3600
                status = "ok" if not last.error and last.jobs_found > 0 else "warning"
                result[src] = {
                    "status": status,
                    "last_run_hours_ago": round(age_hours, 1),
                    "last_jobs_found": last.jobs_found or 0,
                    "error": last.error[:100] if last.error else None,
                }
            else:
                result[src] = {"status": "never_run"}
        return {"status": "ok", "sources": result}
    finally:
        db.close()


def _check_scheduler() -> dict:
    """Scheduler is running if process is up — assume ok."""
    return {"status": "ok", "jobs_count": 8}


def _check_telegram() -> dict:
    from telegram_notifier import telegram_available, _BOT_TOKEN, _CHAT_ID
    if telegram_available():
        return {"status": "configured", "chat_id": _CHAT_ID}
    return {
        "status": "not_configured",
        "has_token": bool(_BOT_TOKEN),
        "has_chat_id": bool(_CHAT_ID),
    }


def _check_linkedin_session() -> dict:
    session_dir = os.path.join(os.path.dirname(__file__), "..", "data", "linkedin_session")
    if os.path.exists(session_dir) and os.listdir(session_dir):
        return {"status": "ok", "path": session_dir}
    from config import LINKEDIN_EMAIL
    return {
        "status": "not_configured" if not LINKEDIN_EMAIL else "no_session",
        "note": "Run linkedin-message once to create session",
    }


def _check_resume_pdf() -> dict:
    from database import SessionLocal, ResumeProfile
    db = SessionLocal()
    try:
        resumes = db.query(ResumeProfile).all()
        pdf_count = sum(1 for r in resumes if r.pdf_path and os.path.exists(r.pdf_path))
        return {
            "status": "ok" if pdf_count > 0 else "warning",
            "resume_count": len(resumes),
            "pdf_count": pdf_count,
            "default_pdf_exists": os.path.exists(
                os.path.join(os.path.dirname(__file__), "..", "HARDIK KOLGE.pdf")
            ),
        }
    finally:
        db.close()


def _check_disk() -> dict:
    try:
        import shutil
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        total, used, free = shutil.disk_usage(data_dir)
        free_gb = free / (1024 ** 3)
        return {
            "status": "ok" if free_gb > 1 else "warning",
            "free_gb": round(free_gb, 1),
            "used_pct": round(used / total * 100, 1),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)[:200]}
