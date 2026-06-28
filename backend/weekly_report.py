"""
Weekly job search report — sent every Monday at 8 AM IST.
Covers the past 7 days: jobs found, applied, responses, interviews, key insights.
Gemini writes the motivational summary section.
"""
import logging
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import PROFILE, SMTP_EMAIL, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, NOTIFY_EMAIL
from database import Application, ApplicationLog, Job, ScrapeLog, SessionLocal

logger = logging.getLogger(__name__)


def send_weekly_report() -> bool:
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        logger.warning("SMTP not set — skipping weekly report")
        return False

    db = SessionLocal()
    try:
        week_ago = datetime.utcnow() - timedelta(days=7)
        stats = _gather_stats(db, week_ago)
        html = _build_html(stats)
        subject = f"GetAJob Weekly Report — {datetime.utcnow().strftime('%b %d, %Y')}"
        return _send(subject, html)
    finally:
        db.close()


def _gather_stats(db, since: datetime) -> dict:
    total_jobs = db.query(Job).count()
    new_this_week = db.query(Job).filter(Job.found_date >= since).count()
    high_match_new = db.query(Job).filter(Job.found_date >= since, Job.match_score >= 80).count()
    applied_this_week = db.query(Job).filter(Job.applied_date >= since).count()
    auto_applied = db.query(Job).filter(Job.applied_date >= since, Job.auto_applied == True).count()
    responses = db.query(Application).filter(
        Application.response_received == True,
        Application.updated_at >= since,
    ).count()
    interviews = db.query(Application).filter(Application.stage == "interview").count()
    offers = db.query(Application).filter(Application.stage == "offer").count()
    pending_followups = db.query(Application).filter(
        Application.email_sent == True,
        Application.response_received == False,
    ).count()
    total_applied = db.query(Job).filter(Job.status == "applied").count()

    # Top 5 best new jobs this week
    top_jobs = (
        db.query(Job)
        .filter(Job.found_date >= since, Job.match_score >= 60, Job.status == "new")
        .order_by(Job.match_score.desc())
        .limit(5)
        .all()
    )

    return {
        "total_jobs": total_jobs,
        "new_this_week": new_this_week,
        "high_match_new": high_match_new,
        "applied_this_week": applied_this_week,
        "auto_applied": auto_applied,
        "responses": responses,
        "interviews": interviews,
        "offers": offers,
        "pending_followups": pending_followups,
        "total_applied": total_applied,
        "top_jobs": top_jobs,
        "week_start": since.strftime("%b %d"),
        "week_end": datetime.utcnow().strftime("%b %d"),
    }


def _build_html(s: dict) -> str:
    # Gemini motivational message
    motivation = ""
    try:
        from gemini import _run, PROFILE_SUMMARY
        prompt = f"""Write a 2-sentence motivational weekly message for a job seeker.
Stats: {s['applied_this_week']} applications sent, {s['responses']} responses, {s['interviews']} interviews.
Candidate: {PROFILE_SUMMARY[:200]}
Be encouraging and specific. No clichés."""
        motivation = _run(prompt, timeout=30)
    except Exception:
        motivation = f"You sent {s['applied_this_week']} applications this week. Keep the momentum going — consistency is the key to landing the right role."

    top_jobs_html = ""
    for j in s["top_jobs"]:
        top_jobs_html += f"""
        <tr>
          <td style="padding:10px 16px;border-bottom:1px solid #e5e7eb;">
            <a href="{j.url}" style="color:#1d4ed8;font-weight:600;text-decoration:none;">{j.title}</a><br>
            <span style="color:#6b7280;font-size:13px;">{j.company} — {j.location}</span>
          </td>
          <td style="padding:10px 16px;border-bottom:1px solid #e5e7eb;text-align:center;">
            <span style="background:{'#16a34a' if j.match_score>=80 else '#f59e0b'};color:#fff;padding:3px 8px;border-radius:12px;font-size:12px;">{j.match_score}</span>
          </td>
          <td style="padding:10px 16px;border-bottom:1px solid #e5e7eb;">
            <a href="{j.url}" style="background:#1d4ed8;color:#fff;padding:5px 12px;border-radius:6px;text-decoration:none;font-size:12px;">Apply</a>
          </td>
        </tr>"""

    return f"""
<html><body style="font-family:-apple-system,sans-serif;background:#f9fafb;margin:0;padding:20px;">
<div style="max-width:680px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.1);">
  <div style="background:linear-gradient(135deg,#1d4ed8,#7c3aed);padding:28px 32px;">
    <h1 style="margin:0;color:#fff;font-size:22px;">GetAJob Weekly Report</h1>
    <p style="margin:8px 0 0;color:#bfdbfe;font-size:14px;">{s['week_start']} – {s['week_end']} · {PROFILE.get('name','')}</p>
  </div>

  <div style="padding:24px 32px;background:#eff6ff;border-bottom:1px solid #dbeafe;">
    <p style="margin:0;color:#1e40af;font-size:15px;line-height:1.6;">{motivation}</p>
  </div>

  <div style="padding:24px 32px;">
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:24px;">
      {_stat_box(s['new_this_week'], 'New Jobs', '#2563eb')}
      {_stat_box(s['applied_this_week'], 'Applied', '#0891b2')}
      {_stat_box(s['responses'], 'Responses', '#16a34a')}
      {_stat_box(s['interviews'], 'Interviews', '#7c3aed')}
    </div>

    <table style="width:100%;border-collapse:collapse;font-size:13px;color:#6b7280;margin-bottom:16px;">
      <tr><td style="padding:4px 0;">Total jobs in DB</td><td style="text-align:right;font-weight:600;color:#374151;">{s['total_jobs']}</td></tr>
      <tr><td style="padding:4px 0;">High-match (80+) new</td><td style="text-align:right;font-weight:600;color:#374151;">{s['high_match_new']}</td></tr>
      <tr><td style="padding:4px 0;">Auto-applied this week</td><td style="text-align:right;font-weight:600;color:#374151;">{s['auto_applied']}</td></tr>
      <tr><td style="padding:4px 0;">Follow-ups pending</td><td style="text-align:right;font-weight:600;color:#374151;">{s['pending_followups']}</td></tr>
      <tr><td style="padding:4px 0;">Offers received</td><td style="text-align:right;font-weight:600;color:{'#16a34a' if s['offers'] else '#374151'};">{s['offers']}</td></tr>
    </table>

    {"<h3 style='font-size:15px;font-weight:600;color:#111827;margin:0 0 12px;'>🔥 Top New Jobs This Week</h3><table style='width:100%;border-collapse:collapse;'><tbody>" + top_jobs_html + "</tbody></table>" if s['top_jobs'] else ""}
  </div>

  <div style="padding:16px 32px;background:#f9fafb;border-top:1px solid #e5e7eb;">
    <p style="margin:0;color:#9ca3af;font-size:12px;">
      View full dashboard: <a href="http://localhost:8000" style="color:#1d4ed8;">http://localhost:8000</a>
    </p>
  </div>
</div>
</body></html>"""


def _stat_box(n, label, color):
    return f'<div style="text-align:center;background:#f9fafb;border-radius:8px;padding:12px;"><div style="font-size:24px;font-weight:700;color:{color};">{n}</div><div style="font-size:11px;color:#6b7280;margin-top:2px;">{label}</div></div>'


def _send(subject: str, html: str) -> bool:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_EMAIL
    msg["To"] = NOTIFY_EMAIL
    msg.attach(MIMEText(html, "html"))
    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as srv:
            srv.login(SMTP_EMAIL, SMTP_PASSWORD)
            srv.sendmail(SMTP_EMAIL, NOTIFY_EMAIL, msg.as_string())
        logger.info(f"Weekly report sent → {NOTIFY_EMAIL}")
        return True
    except Exception as e:
        logger.error(f"Weekly report failed: {e}")
        return False
