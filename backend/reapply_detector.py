"""
Smart re-apply detector.
Identifies applications that:
- Got rejected and were applied >90 days ago (company may have new openings)
- Got no response >60 days ago (worth a fresh attempt with new resume)
Suggests jobs from same companies with newer postings.
"""
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def get_reapply_candidates(db) -> list:
    """Return list of applications worth re-applying to."""
    from database import Application, Job

    now = datetime.utcnow()
    cutoff_no_response = now - timedelta(days=60)
    cutoff_rejected = now - timedelta(days=90)

    suggestions = []

    # No-response applications (60+ days old)
    no_response = (
        db.query(Application)
        .filter(
            Application.email_sent == True,
            Application.response_received == False,
            Application.email_sent_at < cutoff_no_response,
            Application.stage.in_(["applied", "phone_screen"]),
        )
        .all()
    )

    for app in no_response:
        job = db.query(Job).filter(Job.id == app.job_id).first()
        if not job:
            continue
        # Check if company has newer postings
        newer = (
            db.query(Job)
            .filter(
                Job.company == job.company,
                Job.status == "new",
                Job.id != job.id,
            )
            .first()
        )
        days_since = (now - app.email_sent_at).days if app.email_sent_at else 0
        suggestions.append({
            "application_id": app.id,
            "original_job_id": app.job_id,
            "original_title": job.title,
            "company": job.company,
            "days_since_application": days_since,
            "reason": "no_response_60d",
            "newer_job_available": newer.id if newer else None,
            "newer_job_title": newer.title if newer else None,
            "suggestion": f"Re-apply with updated resume — no response in {days_since} days",
        })

    # Rejected applications (90+ days old)
    rejected = (
        db.query(Application)
        .filter(
            Application.stage == "rejected",
            Application.email_sent_at < cutoff_rejected,
        )
        .all()
    )
    for app in rejected:
        job = db.query(Job).filter(Job.id == app.job_id).first()
        if not job:
            continue
        newer = (
            db.query(Job)
            .filter(
                Job.company == job.company,
                Job.status == "new",
                Job.id != job.id,
            )
            .first()
        )
        if not newer:
            continue  # only suggest if newer opening exists
        days_since = (now - app.email_sent_at).days if app.email_sent_at else 0
        suggestions.append({
            "application_id": app.id,
            "original_job_id": app.job_id,
            "original_title": job.title,
            "company": job.company,
            "days_since_application": days_since,
            "reason": "rejected_with_new_opening",
            "newer_job_available": newer.id,
            "newer_job_title": newer.title,
            "suggestion": f"Company has new opening: {newer.title}",
        })

    return sorted(suggestions, key=lambda x: x["days_since_application"], reverse=True)
