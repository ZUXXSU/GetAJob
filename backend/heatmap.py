"""
Application activity heatmap — GitHub-style daily activity calendar.
Shows applications sent + responses received per day for the last 60 days.
"""
from collections import defaultdict
from datetime import datetime, timedelta


def get_heatmap_data(db, days: int = 60) -> dict:
    """Returns: dates list + per-day counts of applications + responses + interviews."""
    from database import Application, ApplicationLog, Job

    end = datetime.utcnow().date()
    start = end - timedelta(days=days)

    # Applications per day
    apps_per_day = defaultdict(int)
    apps = (
        db.query(Application)
        .filter(Application.email_sent == True, Application.email_sent_at >= datetime.combine(start, datetime.min.time()))
        .all()
    )
    for a in apps:
        if a.email_sent_at:
            apps_per_day[a.email_sent_at.date().isoformat()] += 1

    # Responses per day
    resp_per_day = defaultdict(int)
    responses = (
        db.query(Application)
        .filter(Application.response_received == True, Application.response_date >= datetime.combine(start, datetime.min.time()))
        .all()
    )
    for a in responses:
        if a.response_date:
            resp_per_day[a.response_date.date().isoformat()] += 1

    # Interviews per day
    intv_per_day = defaultdict(int)
    interviews = db.query(Application).filter(Application.interview_date != None).all()
    for a in interviews:
        if a.interview_date and a.interview_date.date() >= start:
            intv_per_day[a.interview_date.date().isoformat()] += 1

    # Build daily series
    series = []
    cur = start
    while cur <= end:
        key = cur.isoformat()
        series.append({
            "date": key,
            "day_of_week": cur.strftime("%a"),
            "applications": apps_per_day.get(key, 0),
            "responses": resp_per_day.get(key, 0),
            "interviews": intv_per_day.get(key, 0),
        })
        cur += timedelta(days=1)

    total_apps = sum(d["applications"] for d in series)
    total_resp = sum(d["responses"] for d in series)
    total_intv = sum(d["interviews"] for d in series)
    active_days = sum(1 for d in series if d["applications"] > 0)

    # Best day of week for activity
    dow_totals = defaultdict(int)
    for d in series:
        dow_totals[d["day_of_week"]] += d["applications"]
    best_dow = max(dow_totals.items(), key=lambda x: x[1])[0] if dow_totals else "N/A"

    return {
        "days": days,
        "series": series,
        "totals": {
            "applications": total_apps,
            "responses": total_resp,
            "interviews": total_intv,
            "active_days": active_days,
            "streak": _current_streak(series),
            "best_day_of_week": best_dow,
        },
    }


def _current_streak(series: list) -> int:
    """Consecutive recent days with >= 1 application."""
    streak = 0
    for d in reversed(series):
        if d["applications"] > 0:
            streak += 1
        else:
            break
    return streak
