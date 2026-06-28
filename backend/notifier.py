import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import NOTIFY_EMAIL, PROFILE, SMTP_EMAIL, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT

logger = logging.getLogger(__name__)


def send_digest(jobs: list):
    if not jobs:
        return
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        logger.warning("SMTP not configured — skipping email digest")
        return
    name = PROFILE.get("name", "You")
    subject = f"GetAJob Alert — {len(jobs)} new match(es) for {name}"
    html = _build_html(jobs)
    _send(subject, html)


def _build_html(jobs: list) -> str:
    rows = ""
    for j in jobs:
        if j.match_score >= 80:
            badge_color = "#16a34a"
        elif j.match_score >= 60:
            badge_color = "#d97706"
        else:
            badge_color = "#6b7280"
        rows += f"""
        <tr>
          <td style="padding:12px 16px;border-bottom:1px solid #e5e7eb;vertical-align:top;">
            <a href="{j.url}" style="font-weight:600;color:#1d4ed8;text-decoration:none;font-size:15px;">{j.title}</a><br>
            <span style="color:#374151;font-size:13px;">{j.company}</span><br>
            <span style="color:#6b7280;font-size:12px;">{j.location}</span>
          </td>
          <td style="padding:12px 16px;border-bottom:1px solid #e5e7eb;text-align:center;vertical-align:top;">
            <span style="background:{badge_color};color:#fff;padding:4px 10px;border-radius:12px;font-size:13px;font-weight:600;">{j.match_score}</span>
          </td>
          <td style="padding:12px 16px;border-bottom:1px solid #e5e7eb;color:#059669;font-size:13px;vertical-align:top;">{j.salary_text or "—"}</td>
          <td style="padding:12px 16px;border-bottom:1px solid #e5e7eb;vertical-align:top;">
            <a href="{j.url}" style="background:#1d4ed8;color:#fff;padding:6px 14px;border-radius:6px;text-decoration:none;font-size:13px;">Apply</a>
          </td>
        </tr>"""

    return f"""
<html><body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f9fafb;margin:0;padding:20px;">
  <div style="max-width:700px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.1);">
    <div style="background:#1d4ed8;padding:24px 32px;">
      <h1 style="margin:0;color:#fff;font-size:22px;">GetAJob Daily Digest</h1>
      <p style="margin:6px 0 0;color:#bfdbfe;font-size:14px;">{len(jobs)} new jobs matching your profile</p>
    </div>
    <div style="padding:24px 32px;">
      <table style="width:100%;border-collapse:collapse;">
        <thead>
          <tr style="background:#f3f4f6;">
            <th style="padding:10px 16px;text-align:left;font-size:13px;color:#374151;">Job</th>
            <th style="padding:10px 16px;font-size:13px;color:#374151;">Score</th>
            <th style="padding:10px 16px;text-align:left;font-size:13px;color:#374151;">Salary</th>
            <th style="padding:10px 16px;font-size:13px;color:#374151;">Action</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
    <div style="padding:16px 32px;border-top:1px solid #e5e7eb;background:#f9fafb;">
      <p style="margin:0;color:#9ca3af;font-size:12px;">
        View dashboard at <a href="http://localhost:8000" style="color:#1d4ed8;">http://localhost:8000</a>
      </p>
    </div>
  </div>
</body></html>"""


def _send(subject: str, html: str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_EMAIL
    msg["To"] = NOTIFY_EMAIL
    msg.attach(MIMEText(html, "html"))
    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as srv:
            srv.login(SMTP_EMAIL, SMTP_PASSWORD)
            srv.sendmail(SMTP_EMAIL, NOTIFY_EMAIL, msg.as_string())
        logger.info(f"Digest sent → {NOTIFY_EMAIL}")
    except Exception as e:
        logger.error(f"Email send failed: {e}")
