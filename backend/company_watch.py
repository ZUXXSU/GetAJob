"""
Company watchlist — track specific dream companies.
Alerts user (email + Telegram) when new jobs from watched companies appear.
"""
import json
import logging

logger = logging.getLogger(__name__)


def add_watch(db, company_name: str, role_filter: str = "", min_score: int = 50) -> dict:
    from database import CompanyWatch
    existing = db.query(CompanyWatch).filter_by(company=company_name).first()
    if existing:
        existing.role_filter = role_filter
        existing.min_score = min_score
        db.commit()
        return {"ok": True, "updated": True, "id": existing.id}
    w = CompanyWatch(company=company_name, role_filter=role_filter, min_score=min_score)
    db.add(w)
    db.commit()
    db.refresh(w)
    return {"ok": True, "created": True, "id": w.id}


def remove_watch(db, watch_id: int) -> bool:
    from database import CompanyWatch
    w = db.query(CompanyWatch).filter_by(id=watch_id).first()
    if not w:
        return False
    db.delete(w)
    db.commit()
    return True


def list_watches(db) -> list:
    from database import CompanyWatch, Job
    watches = db.query(CompanyWatch).all()
    result = []
    for w in watches:
        # Count current matching jobs
        q = db.query(Job).filter(Job.company.ilike(f"%{w.company}%"), Job.match_score >= w.min_score)
        if w.role_filter:
            q = q.filter(Job.title.ilike(f"%{w.role_filter}%"))
        matches = q.all()
        new_count = sum(1 for j in matches if j.status == "new")
        result.append({
            "id": w.id,
            "company": w.company,
            "role_filter": w.role_filter,
            "min_score": w.min_score,
            "total_jobs": len(matches),
            "new_jobs": new_count,
            "best_match": (
                {"id": matches[0].id, "title": matches[0].title, "score": matches[0].match_score}
                if matches else None
            ),
            "last_alerted_at": w.last_alerted_at.isoformat() if w.last_alerted_at else None,
        })
    return result


def check_alerts(db) -> int:
    """Check watchlist for new matching jobs since last alert. Send notifications."""
    from datetime import datetime
    from database import CompanyWatch, Job
    from telegram_notifier import send as tg_send

    watches = db.query(CompanyWatch).all()
    alerts_sent = 0

    for w in watches:
        q = db.query(Job).filter(
            Job.company.ilike(f"%{w.company}%"),
            Job.match_score >= w.min_score,
            Job.status == "new",
        )
        if w.role_filter:
            q = q.filter(Job.title.ilike(f"%{w.role_filter}%"))
        if w.last_alerted_at:
            q = q.filter(Job.found_date > w.last_alerted_at)

        new_jobs = q.all()
        if new_jobs:
            # Send Telegram alert
            msg = f"⭐ <b>Watchlist alert: {w.company}</b>\n{len(new_jobs)} new matching role(s):\n\n"
            for j in new_jobs[:3]:
                msg += f"• <b>{j.title}</b> (score {j.match_score})\n  <a href='{j.url}'>Apply</a>\n"
            tg_send(msg)
            w.last_alerted_at = datetime.utcnow()
            db.commit()
            alerts_sent += 1
            logger.info(f"Watchlist alert: {w.company} ({len(new_jobs)} new)")

    return alerts_sent
