"""
Response time analytics.
Measures: median days to first response, by source, day-of-week, hour-of-day.
Tells the user: "Tuesday 10 AM apps get 2× more responses".
"""
import logging
from collections import defaultdict
from datetime import datetime

logger = logging.getLogger(__name__)


def compute_response_analytics(db) -> dict:
    """Compute response-time stats across applications."""
    from database import Application, Job

    apps = db.query(Application).filter(Application.email_sent == True).all()
    if not apps:
        return {"total": 0, "message": "No applications sent yet"}

    response_times = []
    by_source = defaultdict(lambda: {"sent": 0, "responses": 0, "times": []})
    by_dow = defaultdict(lambda: {"sent": 0, "responses": 0, "times": []})
    by_hour = defaultdict(lambda: {"sent": 0, "responses": 0, "times": []})

    for app in apps:
        if not app.email_sent_at:
            continue
        job = db.query(Job).filter_by(id=app.job_id).first()
        src = (job.source if job else "unknown")
        dow = app.email_sent_at.strftime("%a")
        hour = app.email_sent_at.hour

        by_source[src]["sent"] += 1
        by_dow[dow]["sent"] += 1
        by_hour[hour]["sent"] += 1

        if app.response_received and app.response_date:
            days = (app.response_date - app.email_sent_at).total_seconds() / 86400
            response_times.append(days)
            by_source[src]["responses"] += 1
            by_source[src]["times"].append(days)
            by_dow[dow]["responses"] += 1
            by_dow[dow]["times"].append(days)
            by_hour[hour]["responses"] += 1
            by_hour[hour]["times"].append(days)

    # Median helper
    def median(xs):
        if not xs:
            return 0
        s = sorted(xs)
        n = len(s)
        return round(s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2, 1)

    overall_response_rate = round(len(response_times) / len(apps) * 100, 1)
    median_days = median(response_times)

    # Best day, hour, source
    def with_rates(d):
        result = {}
        for k, v in d.items():
            v["response_rate"] = round(v["responses"] / max(v["sent"], 1) * 100, 1)
            v["median_days"] = median(v["times"])
            v.pop("times", None)
            result[k] = v
        return result

    by_source_clean = with_rates(by_source)
    by_dow_clean = with_rates(by_dow)
    by_hour_clean = with_rates(by_hour)

    # Find best (min sample size 3 for confidence)
    def best(d, key="response_rate", min_sent=3):
        qualified = {k: v for k, v in d.items() if v["sent"] >= min_sent}
        if not qualified:
            return None
        return max(qualified.items(), key=lambda x: x[1][key])

    best_dow = best(by_dow_clean)
    best_hour = best(by_hour_clean)
    best_source = best(by_source_clean)

    insights = []
    if best_dow:
        insights.append(
            f"📅 {best_dow[0]} applications get {best_dow[1]['response_rate']}% response rate (vs {overall_response_rate}% overall)"
        )
    if best_hour:
        insights.append(
            f"🕐 Sending at {best_hour[0]:02d}:00 gets {best_hour[1]['response_rate']}% response rate"
        )
    if best_source:
        insights.append(
            f"🌐 Source '{best_source[0]}' has the highest response rate ({best_source[1]['response_rate']}%)"
        )
    if median_days:
        insights.append(
            f"⏱ Median response time: {median_days} days. If no response by day {int(median_days * 2)}, send follow-up."
        )

    return {
        "total_sent": len(apps),
        "total_responses": len(response_times),
        "response_rate_pct": overall_response_rate,
        "median_days_to_response": median_days,
        "by_source": by_source_clean,
        "by_day_of_week": by_dow_clean,
        "by_hour": by_hour_clean,
        "insights": insights,
    }
