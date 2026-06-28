"""
LinkedIn automation — sends connection requests + messages to HR/recruiters.
Uses Playwright browser automation. Requires LinkedIn credentials in .env.
All actions logged to LinkedInLog table.
"""
import logging
import os
import time
from datetime import datetime

from config import LINKEDIN_EMAIL, LINKEDIN_PASSWORD, PROFILE
from database import LinkedInLog, SessionLocal

logger = logging.getLogger(__name__)


def _get_browser():
    from playwright.sync_api import sync_playwright
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=True)
    return p, browser


def linkedin_available() -> bool:
    return bool(LINKEDIN_EMAIL and LINKEDIN_PASSWORD)


def find_recruiter_and_message(
    company: str,
    job_title: str,
    job_id: int,
    message_template: str = "",
    dry_run: bool = True,
) -> dict:
    """
    Search LinkedIn for recruiter/HR at the company and send connection + message.
    Returns: {status, recruiter_name, recruiter_url, message_sent}
    """
    if not linkedin_available():
        return {"status": "skipped", "reason": "No LinkedIn credentials in .env"}

    db = SessionLocal()
    try:
        # Check if already messaged this company
        existing = db.query(LinkedInLog).filter_by(job_id=job_id).first()
        if existing and existing.message_sent:
            return {"status": "already_sent", "recruiter_url": existing.recruiter_url}

        log = LinkedInLog(
            job_id=job_id,
            company=company,
            status="started",
        )
        db.add(log)
        db.commit()

        if dry_run:
            log.status = "dry_run"
            log.message_sent = False
            db.commit()
            return {"status": "dry_run", "message": f"Would search LinkedIn for HR at {company}"}

        try:
            result = _do_linkedin_action(company, job_title, message_template, log, db)
            return result
        except Exception as e:
            log.status = f"error: {str(e)[:200]}"
            db.commit()
            logger.error(f"LinkedIn error for {company}: {e}")
            return {"status": "error", "error": str(e)}
    finally:
        db.close()


def _do_linkedin_action(company: str, job_title: str, message: str, log, db) -> dict:
    from playwright.sync_api import sync_playwright

    p, browser = None, None
    try:
        p = sync_playwright().__enter__()
        context = p.chromium.launch_persistent_context(
            user_data_dir=os.path.join(os.path.dirname(__file__), '..', 'data', 'linkedin_session'),
            headless=True,
            viewport={"width": 1280, "height": 720},
        )
        page = context.new_page()

        # Check if already logged in
        page.goto("https://www.linkedin.com/feed/", timeout=20000)
        if "login" in page.url or "checkpoint" in page.url:
            _login(page)

        # Search for recruiter/HR at company
        search_url = (
            f"https://www.linkedin.com/search/results/people/"
            f"?keywords=recruiter+{company}&origin=GLOBAL_SEARCH_HEADER"
        )
        page.goto(search_url, timeout=20000)
        time.sleep(2)

        # Find first result
        profiles = page.query_selector_all(".entity-result__title-text a")
        if not profiles:
            log.status = "no_recruiter_found"
            db.commit()
            return {"status": "no_recruiter_found", "company": company}

        first = profiles[0]
        recruiter_name = first.inner_text().strip()
        recruiter_url = first.get_attribute("href", "").split("?")[0]

        log.recruiter_name = recruiter_name
        log.recruiter_url = recruiter_url
        db.commit()

        # Go to profile and send connection with note
        page.goto(recruiter_url, timeout=20000)
        time.sleep(2)

        connect_btn = page.query_selector("button[aria-label*='Connect']")
        if not connect_btn:
            # Try "More" menu
            more = page.query_selector("button[aria-label*='More actions']")
            if more:
                more.click()
                time.sleep(0.5)
                connect_opt = page.query_selector("div[aria-label*='Connect']")
                if connect_opt:
                    connect_opt.click()

        # Add note to connection request
        add_note = page.query_selector("button[aria-label='Add a note']")
        if add_note:
            add_note.click()
            time.sleep(0.5)
            note_box = page.query_selector("textarea[name='message']")
            if note_box and message:
                note_box.fill(message[:300])
            send = page.query_selector("button[aria-label='Send now']")
            if send:
                send.click()
                time.sleep(1)

        log.status = "sent"
        log.message_sent = True
        log.message_text = message[:500]
        log.sent_at = datetime.utcnow()
        db.commit()

        context.close()
        p.__exit__(None, None, None)
        return {"status": "sent", "recruiter_name": recruiter_name, "recruiter_url": recruiter_url}

    except Exception as e:
        if p:
            try:
                p.__exit__(None, None, None)
            except Exception:
                pass
        raise


def _login(page):
    """Perform LinkedIn login."""
    page.goto("https://www.linkedin.com/login", timeout=15000)
    page.fill("#username", LINKEDIN_EMAIL)
    page.fill("#password", LINKEDIN_PASSWORD)
    page.click("button[type='submit']")
    page.wait_for_load_state("networkidle", timeout=15000)
    if "challenge" in page.url or "checkpoint" in page.url:
        raise Exception("LinkedIn CAPTCHA/2FA required — log in manually once via a browser at data/linkedin_session")


def generate_linkedin_message(job_title: str, company: str, cover_letter_snippet: str = "") -> str:
    """Generate a short LinkedIn connection note (max 300 chars)."""
    from config import PROFILE
    name = PROFILE.get("name", "")
    exp = PROFILE.get("experience_years", 1)
    skills = PROFILE.get("skills", [])
    top_skills = "/".join(s.title() for s in skills[:3])
    msg = (
        f"Hi, I'm {name}, a {top_skills} developer with {exp}yr experience. "
        f"Interested in the {job_title} role at {company}. "
        f"Would love to connect!"
    )
    return msg[:300]
