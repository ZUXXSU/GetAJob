"""
Export application and job data to CSV format.
Returns CSV string ready to write to file or stream as HTTP response.
"""
import csv
import io
from datetime import datetime


def export_applications_csv(db) -> str:
    from database import Application, Job
    apps = db.query(Application).all()
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow([
        "ID", "Job Title", "Company", "Location", "Score", "Stage",
        "HR Email", "Applied Date", "Response Received", "Response Date",
        "Follow-up Count", "Interview Date", "Offer Amount", "Notes",
    ])
    for app in apps:
        job = db.query(Job).filter(Job.id == app.job_id).first()
        writer.writerow([
            app.id,
            job.title if job else "",
            job.company if job else "",
            job.location if job else "",
            job.match_score if job else "",
            app.stage,
            app.hr_email or "",
            app.email_sent_at.strftime("%Y-%m-%d") if app.email_sent_at else "",
            "Yes" if app.response_received else "No",
            app.response_date.strftime("%Y-%m-%d") if getattr(app, "response_date", None) else "",
            app.follow_up_count or 0,
            app.interview_date.strftime("%Y-%m-%d") if getattr(app, "interview_date", None) else "",
            getattr(app, "offer_amount", "") or "",
            app.notes or "",
        ])
    return out.getvalue()


def export_jobs_csv(db, min_score: int = 60) -> str:
    from database import Job, AIAnalysis
    jobs = (
        db.query(Job)
        .filter(Job.match_score >= min_score)
        .order_by(Job.match_score.desc())
        .all()
    )
    analyses = {a.job_id: a for a in db.query(AIAnalysis).all()}
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow([
        "ID", "Title", "Company", "Location", "Source", "Score", "AI Score",
        "Salary", "Status", "Apply Recommended", "Found Date", "URL",
    ])
    for j in jobs:
        ai = analyses.get(j.id)
        writer.writerow([
            j.id, j.title, j.company, j.location, j.source,
            j.match_score, ai.ai_score if ai else "",
            j.salary_text or "",
            j.status,
            "Yes" if (ai and ai.apply_recommended) else ("No" if ai else ""),
            j.found_date.strftime("%Y-%m-%d") if j.found_date else "",
            j.url,
        ])
    return out.getvalue()
