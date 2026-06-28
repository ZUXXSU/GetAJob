"""
Telegram bot notifications — instant alerts for high-score jobs, applications sent,
interview requests, and daily summaries.
Setup: create bot via @BotFather → get token → set TELEGRAM_BOT_TOKEN in .env
       message your bot → get chat id via /api/telegram/setup
"""
import logging
import os

import requests

from config import PROFILE

logger = logging.getLogger(__name__)

_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
_API = "https://api.telegram.org/bot"


def telegram_available() -> bool:
    return bool(_BOT_TOKEN and _CHAT_ID)


def send(message: str, parse_mode: str = "HTML") -> bool:
    """Send via Telegram + WhatsApp (if both configured)."""
    sent = False
    # Telegram
    if telegram_available():
        try:
            r = requests.post(
                f"{_API}{_BOT_TOKEN}/sendMessage",
                json={"chat_id": _CHAT_ID, "text": message, "parse_mode": parse_mode},
                timeout=8,
            )
            sent = r.ok or sent
        except Exception as e:
            logger.debug(f"Telegram send failed: {e}")

    # WhatsApp (strip HTML)
    try:
        from whatsapp_notifier import send_whatsapp, whatsapp_available
        if whatsapp_available():
            import re
            plain = re.sub(r'<[^>]+>', '', message)
            sent = send_whatsapp(plain) or sent
    except Exception:
        pass

    # Slack (strip HTML)
    try:
        from slack_notifier import send_slack, slack_available
        if slack_available():
            import re
            plain = re.sub(r'<[^>]+>', '', message)
            sent = send_slack(plain) or sent
    except Exception:
        pass

    return sent


def get_chat_id(token: str) -> str:
    """Fetch the latest chat ID from the bot's updates (call after messaging the bot)."""
    try:
        r = requests.get(f"{_API}{token}/getUpdates", timeout=8)
        data = r.json()
        updates = data.get("result", [])
        if updates:
            return str(updates[-1]["message"]["chat"]["id"])
    except Exception:
        pass
    return ""


# ── Notification templates ────────────────────────────────────────────────────

def notify_high_score_jobs(jobs: list):
    if not jobs or not telegram_available():
        return
    name = PROFILE.get("name", "")
    lines = [f"🔥 <b>GetAJob — {len(jobs)} High-Match Jobs Found!</b>\n"]
    for j in jobs[:5]:
        lines.append(
            f"<b>{j.title}</b> @ {j.company}\n"
            f"📍 {j.location} | ⭐ {j.match_score}\n"
            f"🔗 <a href='{j.url}'>Apply</a>\n"
        )
    if len(jobs) > 5:
        lines.append(f"...and {len(jobs) - 5} more → http://localhost:8000")
    send("\n".join(lines))


def notify_application_sent(job, hr_email: str, resume_name: str = ""):
    if not telegram_available():
        return
    send(
        f"✅ <b>Application Sent!</b>\n"
        f"<b>{job.title}</b> @ {job.company}\n"
        f"📧 → {hr_email}\n"
        f"📄 Resume: {resume_name or 'Default'}\n"
        f"📊 Score: {job.match_score}"
    )


def notify_interview_detected(job, stage: str):
    if not telegram_available():
        return
    send(
        f"🎉 <b>Interview Opportunity!</b>\n"
        f"<b>{job.title}</b> @ {job.company}\n"
        f"Stage: {stage.replace('_', ' ').title()}\n"
        f"🔗 Dashboard: http://localhost:8000"
    )


def notify_daily_summary(stats: dict):
    if not telegram_available():
        return
    send(
        f"📊 <b>GetAJob Daily Summary</b>\n"
        f"🔍 Total Jobs: {stats.get('total', 0)}\n"
        f"🆕 New Today: {stats.get('new_today', 0)}\n"
        f"📨 Applied: {stats.get('applied', 0)}\n"
        f"🤖 Auto-Applied: {stats.get('auto_applied', 0)}\n"
        f"⭐ High Match (80+): {stats.get('high_match', 0)}\n"
        f"💬 Follow-ups Sent: {stats.get('followups_sent', 0)}\n"
        f"🎯 Interviews: {stats.get('interviews', 0)}"
    )


def notify_scrape_complete(new_count: int, high_score_count: int):
    if not telegram_available() or new_count == 0:
        return
    msg = f"🔄 Scrape complete: <b>{new_count} new jobs</b>"
    if high_score_count:
        msg += f", <b>{high_score_count} high-match (80+)</b> 🔥"
    send(msg)
