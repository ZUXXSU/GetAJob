import logging
import time
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from bs4 import BeautifulSoup

from config import (AUTO_APPLY_ENABLED, AUTO_APPLY_INTERVAL_HOURS,
                    BLACKLIST_COMPANIES, BLACKLIST_KEYWORDS,
                    DIGEST_EMAIL_HOUR, PROFILE, SCRAPE_INTERVAL_HOURS,
                    WEEKLY_REPORT_ENABLED)
from database import Job, ScrapeLog, SessionLocal
from deduplicator import is_duplicate
from matcher import parse_salary, score_job
from notifier import send_digest
from scrapers.adzuna import AdzunaScraper
from scrapers.jsearch import JSearchScraper
from scrapers.linkedin import LinkedInScraper
from scrapers.naukri import NaukriScraper
from scrapers.remoteok import RemoteOKScraper
from scrapers.remotive import RemotiveScraper
from scrapers.rss_jobs import RSSScraper
from telegram_notifier import (notify_high_score_jobs, notify_scrape_complete,
                                notify_daily_summary)

logger = logging.getLogger(__name__)

_SCRAPER_QUERIES = {
    "adzuna": PROFILE["search_queries"],
    "jsearch": ["flutter developer", "ios developer swift", "mobile developer"],
    "naukri": PROFILE["search_queries"],
    "linkedin": ["flutter developer", "ios developer", "mobile developer", "full stack developer"],
    "remotive": ["flutter developer", "ios developer swift", "mobile developer", "full stack developer"],
    "remoteok": ["flutter developer", "ios developer swift", "mobile developer", "react native developer"],
    "rss": ["flutter", "mobile", "ios"],
}

SCRAPERS = [AdzunaScraper(), JSearchScraper(), NaukriScraper(), LinkedInScraper(),
            RemotiveScraper(), RemoteOKScraper(), RSSScraper()]


def run_all_scrapers():
    logger.info("Scrape cycle started")
    db = SessionLocal()
    total_new = 0
    high_score_new = []
    try:
        for scraper in SCRAPERS:
            queries = _SCRAPER_QUERIES.get(scraper.name, PROFILE["search_queries"])
            for query in queries:
                new, high = _scrape_one(scraper, query, db)
                total_new += new
                high_score_new.extend(high)
                time.sleep(1.5)
    finally:
        db.close()

    logger.info(f"Scrape complete: {total_new} new jobs")
    # Telegram alerts
    notify_scrape_complete(total_new, len(high_score_new))
    if high_score_new:
        notify_high_score_jobs(high_score_new)
    # Check watchlist for new matches
    try:
        from company_watch import check_alerts
        db2 = SessionLocal()
        try:
            check_alerts(db2)
        finally:
            db2.close()
    except Exception as e:
        logger.warning(f"Watchlist alert check failed: {e}")


def _scrape_one(scraper, query: str, db) -> tuple:
    """Returns (new_count, list_of_high_score_jobs)."""
    start = datetime.utcnow()
    log = ScrapeLog(source=scraper.name)
    db.add(log)
    db.commit()
    new_count = 0
    high_score_jobs = []
    try:
        raw_jobs = scraper.safe_fetch(query)
        for rj in raw_jobs:
            ext_id = rj.get("external_id", "")
            # Dedup by external_id (same source)
            if ext_id and db.query(Job).filter_by(source=scraper.name, external_id=ext_id).first():
                continue
            # Dedup by title+company across sources
            title = rj.get("title", "")
            company = rj.get("company", "")
            if title and company and is_duplicate(title, company, db):
                continue

            # Blacklist filter
            company_lower = company.lower()
            desc_lower = (rj.get("description", "") or "").lower()
            title_lower = title.lower()
            if any(b in company_lower for b in BLACKLIST_COMPANIES if b):
                continue
            if any(b in desc_lower or b in title_lower for b in BLACKLIST_KEYWORDS if b):
                continue

            raw_desc = rj.get("description", "")
            clean_desc = (
                BeautifulSoup(raw_desc, "lxml").get_text(separator=" ")
                if "<" in raw_desc else raw_desc
            )
            sal_min, sal_max = parse_salary(rj.get("salary_text", ""))
            if rj.get("salary_min") is not None:
                sal_min = rj["salary_min"]
            if rj.get("salary_max") is not None:
                sal_max = rj["salary_max"]
            score = score_job(title, clean_desc, rj.get("location", ""), sal_min)
            if score < 20:
                continue

            job = Job(
                source=rj.get("source", scraper.name),
                external_id=ext_id,
                title=title,
                company=company,
                location=rj.get("location", ""),
                salary_min=sal_min,
                salary_max=sal_max,
                salary_text=rj.get("salary_text", ""),
                description=clean_desc[:4000],
                url=rj.get("url", ""),
                match_score=score,
            )
            db.add(job)
            new_count += 1
            if score >= 80:
                high_score_jobs.append(job)

        db.commit()
        log.jobs_found = len(raw_jobs)
        log.jobs_new = new_count
        log.duration_seconds = (datetime.utcnow() - start).total_seconds()
        db.commit()
        if new_count > 0:
            logger.info(f"[{scraper.name}] '{query}': {len(raw_jobs)} found, {new_count} new")
    except Exception as e:
        log.error = str(e)
        log.duration_seconds = (datetime.utcnow() - start).total_seconds()
        db.commit()
        logger.error(f"[{scraper.name}] '{query}' error: {e}")

    return new_count, high_score_jobs


def send_daily_digest():
    db = SessionLocal()
    try:
        jobs = (
            db.query(Job)
            .filter(Job.status == "new", Job.match_score >= 60, Job.notified == False)
            .order_by(Job.match_score.desc())
            .limit(25)
            .all()
        )
        if jobs:
            send_digest(jobs)
            for j in jobs:
                j.notified = True
            db.commit()
            logger.info(f"Digest sent — {len(jobs)} jobs")

        # Telegram daily summary
        from database import Application
        total = db.query(Job).count()
        new = db.query(Job).filter(Job.status == "new").count()
        applied = db.query(Job).filter(Job.status == "applied").count()
        auto_applied = db.query(Job).filter(Job.auto_applied == True).count()
        high_match = db.query(Job).filter(Job.match_score >= 80).count()
        interviews = db.query(Application).filter(Application.stage == "interview").count()
        notify_daily_summary({
            "total": total, "new_today": len(jobs), "applied": applied,
            "auto_applied": auto_applied, "high_match": high_match,
            "followups_sent": 0, "interviews": interviews,
        })
    finally:
        db.close()


def run_auto_apply_cycle():
    if not AUTO_APPLY_ENABLED:
        return
    from auto_apply import run_auto_apply
    logger.info("Auto-apply cycle started")
    stats = run_auto_apply(dry_run=False)
    logger.info(f"Auto-apply cycle: {stats}")


def run_followup_cycle():
    """Send follow-up emails for applications with no response after 7/14 days."""
    from followup import run_followups
    logger.info("Follow-up cycle started")
    stats = run_followups(dry_run=False)
    if stats.get("sent", 0) > 0:
        logger.info(f"Follow-ups sent: {stats}")


def send_weekly_report():
    """Weekly summary email every Monday at 8 AM IST."""
    if not WEEKLY_REPORT_ENABLED:
        return
    from weekly_report import send_weekly_report as _send
    logger.info("Sending weekly report...")
    _send()


def run_weekly_backup():
    """Auto-backup DB + resumes every Sunday."""
    try:
        from backup_restore import create_backup
        result = create_backup()
        if result.get("ok"):
            logger.info(f"Weekly backup: {result['filename']} ({result['size_mb']}MB)")
    except Exception as e:
        logger.warning(f"Backup failed: {e}")


def check_email_replies():
    """Scan Gmail inbox for replies to applications."""
    try:
        from reply_detector import check_for_replies
        result = check_for_replies(dry_run=False)
        if result.get("updated_apps", 0) > 0:
            logger.info(f"Reply check: {result}")
    except Exception as e:
        logger.warning(f"Reply check failed: {e}")


def cleanup_old_data():
    """Remove old low-score jobs every week to keep DB lean."""
    from recommender import cleanup_old_jobs
    db = SessionLocal()
    try:
        n = cleanup_old_jobs(db, days=60)
        if n > 0:
            logger.info(f"Weekly cleanup: removed {n} stale jobs")
    finally:
        db.close()


def send_morning_applications():
    """
    Optimal send time: 9 AM IST weekdays.
    If auto-apply ran overnight and queued jobs, send them now at peak HR reading time.
    This is an additional cycle — not the only trigger.
    """
    if not AUTO_APPLY_ENABLED:
        return
    from auto_apply import run_auto_apply
    logger.info("Morning optimal-time application cycle")
    run_auto_apply(dry_run=False)


def setup_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="Asia/Kolkata")

    # Core scrape cycle
    scheduler.add_job(
        run_all_scrapers,
        IntervalTrigger(hours=SCRAPE_INTERVAL_HOURS),
        id="scrape", replace_existing=True, misfire_grace_time=600,
    )

    # Email digest at configured hour
    scheduler.add_job(
        send_daily_digest,
        CronTrigger(hour=DIGEST_EMAIL_HOUR, minute=0, timezone="Asia/Kolkata"),
        id="digest", replace_existing=True,
    )

    # Auto-apply cycle (only if enabled)
    scheduler.add_job(
        run_auto_apply_cycle,
        IntervalTrigger(hours=AUTO_APPLY_INTERVAL_HOURS),
        id="auto_apply", replace_existing=True,
    )

    # Optimal morning send: 9 AM IST Mon-Fri
    scheduler.add_job(
        send_morning_applications,
        CronTrigger(hour=9, minute=0, day_of_week="mon-fri", timezone="Asia/Kolkata"),
        id="morning_apply", replace_existing=True,
    )

    # Follow-up check: daily at 10 AM IST
    scheduler.add_job(
        run_followup_cycle,
        CronTrigger(hour=10, minute=0, timezone="Asia/Kolkata"),
        id="followups", replace_existing=True,
    )

    # Weekly report: every Monday at 8 AM IST
    scheduler.add_job(
        send_weekly_report,
        CronTrigger(day_of_week="mon", hour=8, minute=0, timezone="Asia/Kolkata"),
        id="weekly_report", replace_existing=True,
    )

    # Weekly cleanup: every Sunday at 3 AM IST
    scheduler.add_job(
        cleanup_old_data,
        CronTrigger(day_of_week="sun", hour=3, minute=0, timezone="Asia/Kolkata"),
        id="cleanup", replace_existing=True,
    )

    # Check email replies every 2 hours
    scheduler.add_job(
        check_email_replies,
        IntervalTrigger(hours=2),
        id="reply_check", replace_existing=True,
    )

    # Weekly backup: every Sunday at 4 AM IST
    scheduler.add_job(
        run_weekly_backup,
        CronTrigger(day_of_week="sun", hour=4, minute=0, timezone="Asia/Kolkata"),
        id="backup", replace_existing=True,
    )

    return scheduler
