"""
iCalendar (.ics) export for interview schedules + follow-up reminders.
Lets candidate add interview dates and follow-up reminders to any calendar app
(Google Calendar, Apple Calendar, Outlook).
"""
from datetime import datetime, timedelta


def _ics_escape(s: str) -> str:
    return (s or "").replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


def _format_dt(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%SZ")


def build_calendar_ics(db) -> str:
    """Build a full ICS feed of all interviews + follow-up reminders."""
    from database import Application, Job

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//GetAJob//Enterprise//EN",
        "CALSCALE:GREGORIAN",
        "X-WR-CALNAME:GetAJob Job Search",
    ]

    apps = db.query(Application).all()
    for app in apps:
        job = db.query(Job).filter(Job.id == app.job_id).first()
        if not job:
            continue

        # Interview event
        if app.interview_date:
            uid = f"interview-{app.id}@getajob"
            start = app.interview_date
            end = start + timedelta(hours=1)
            lines += [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{_format_dt(datetime.utcnow())}",
                f"DTSTART:{_format_dt(start)}",
                f"DTEND:{_format_dt(end)}",
                f"SUMMARY:Interview — {_ics_escape(job.title)} @ {_ics_escape(job.company)}",
                f"DESCRIPTION:{_ics_escape(job.title)} interview at {_ics_escape(job.company)}\\nApply URL: {_ics_escape(job.url or '')}",
                "BEGIN:VALARM",
                "TRIGGER:-PT1H",
                "ACTION:DISPLAY",
                f"DESCRIPTION:Interview with {_ics_escape(job.company)} in 1 hour",
                "END:VALARM",
                "END:VEVENT",
            ]

        # Follow-up reminders (if applicable)
        if app.email_sent_at and not app.response_received and (app.follow_up_count or 0) < 2:
            days_due = 7 if (app.follow_up_count or 0) == 0 else 14
            due = app.email_sent_at + timedelta(days=days_due)
            if due > datetime.utcnow():
                uid = f"followup-{app.id}-{app.follow_up_count or 0}@getajob"
                lines += [
                    "BEGIN:VEVENT",
                    f"UID:{uid}",
                    f"DTSTAMP:{_format_dt(datetime.utcnow())}",
                    f"DTSTART:{_format_dt(due)}",
                    f"DTEND:{_format_dt(due + timedelta(minutes=30))}",
                    f"SUMMARY:Follow-up — {_ics_escape(job.title)} @ {_ics_escape(job.company)}",
                    f"DESCRIPTION:Send follow-up #{(app.follow_up_count or 0)+1} to {_ics_escape(app.hr_email or '')}",
                    "END:VEVENT",
                ]

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)


def single_interview_ics(application_id: int, interview_date_str: str, db) -> str:
    """Build ICS for a single interview (for one-click 'Add to Calendar' link)."""
    from database import Application, Job
    app = db.query(Application).filter(Application.id == application_id).first()
    if not app:
        return ""
    job = db.query(Job).filter(Job.id == app.job_id).first()
    if not job:
        return ""

    try:
        start = datetime.fromisoformat(interview_date_str)
    except Exception:
        start = datetime.utcnow() + timedelta(days=1)
    end = start + timedelta(hours=1)

    return "\r\n".join([
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//GetAJob//Enterprise//EN",
        "BEGIN:VEVENT",
        f"UID:single-{application_id}-{int(start.timestamp())}@getajob",
        f"DTSTAMP:{_format_dt(datetime.utcnow())}",
        f"DTSTART:{_format_dt(start)}",
        f"DTEND:{_format_dt(end)}",
        f"SUMMARY:Interview — {_ics_escape(job.title)} @ {_ics_escape(job.company)}",
        f"DESCRIPTION:{_ics_escape(job.title)} at {_ics_escape(job.company)}\\nLink: {_ics_escape(job.url or '')}",
        "BEGIN:VALARM",
        "TRIGGER:-PT1H",
        "ACTION:DISPLAY",
        "DESCRIPTION:Interview in 1 hour",
        "END:VALARM",
        "END:VEVENT",
        "END:VCALENDAR",
    ])
