"""
Achievement system — gamifies the job search to build daily habit.
Badges unlocked at meaningful milestones. Drives the most predictive behavior:
consistency.
"""
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


BADGES = [
    # Application milestones
    {"id": "first_app", "title": "First Step", "icon": "👶", "desc": "Sent first application", "category": "applications"},
    {"id": "ten_apps", "title": "Decimator", "icon": "🔟", "desc": "Sent 10 applications", "category": "applications"},
    {"id": "fifty_apps", "title": "Persistent", "icon": "💪", "desc": "Sent 50 applications", "category": "applications"},
    {"id": "hundred_apps", "title": "Centurion", "icon": "💯", "desc": "Sent 100 applications", "category": "applications"},

    # Pipeline progression
    {"id": "first_response", "title": "Listened", "icon": "👂", "desc": "Got first response", "category": "pipeline"},
    {"id": "first_interview", "title": "Foot in Door", "icon": "🚪", "desc": "First interview scheduled", "category": "pipeline"},
    {"id": "five_interviews", "title": "Interview Master", "icon": "🎯", "desc": "5+ interviews", "category": "pipeline"},
    {"id": "first_offer", "title": "Job Hunter", "icon": "🏆", "desc": "First offer received!", "category": "pipeline"},

    # Consistency
    {"id": "week_streak", "title": "Week Warrior", "icon": "🔥", "desc": "7-day coding streak", "category": "consistency"},
    {"id": "month_streak", "title": "Marathon", "icon": "🏃", "desc": "30-day coding streak", "category": "consistency"},
    {"id": "daily_player", "title": "Daily Player", "icon": "📅", "desc": "Applied 5 days in a row", "category": "consistency"},

    # AI usage
    {"id": "ai_analyzed_50", "title": "AI Power User", "icon": "✨", "desc": "Analyzed 50+ jobs with Gemini", "category": "ai"},
    {"id": "ai_recommended_resume", "title": "Tailored", "icon": "🎨", "desc": "Generated tailored resume", "category": "ai"},

    # Network
    {"id": "first_outreach", "title": "Network Starter", "icon": "🌐", "desc": "Sent first cold outreach", "category": "network"},
    {"id": "ten_outreach", "title": "Connector", "icon": "🤝", "desc": "10+ outreach messages", "category": "network"},

    # Resume variety
    {"id": "three_resumes", "title": "Versatile", "icon": "📋", "desc": "Created 3+ resume variants", "category": "resume"},

    # Quality
    {"id": "high_match_app", "title": "Sharpshooter", "icon": "🎯", "desc": "Applied to 80+ match job", "category": "quality"},
    {"id": "follow_up_sent", "title": "Persistent Pro", "icon": "📨", "desc": "Sent follow-up email", "category": "quality"},
]


def get_unlocked(db) -> dict:
    """Compute unlocked badges + progress on locked ones."""
    from database import (Application, AIAnalysis, CodingPractice, Job, OutreachLog,
                          ResumeProfile)

    total_applied = db.query(Job).filter(Job.status == "applied").count()
    responses = db.query(Application).filter(Application.response_received == True).count()
    interviews = db.query(Application).filter(Application.stage == "interview").count()
    offers = db.query(Application).filter(Application.stage == "offer").count()
    ai_analyzed = db.query(AIAnalysis).count()
    outreach_count = db.query(OutreachLog).count()
    resume_count = db.query(ResumeProfile).count()
    coding_streak = _coding_streak(db)
    apply_streak = _apply_streak(db)
    high_match_apps = (
        db.query(Job)
        .filter(Job.match_score >= 80, Job.status == "applied")
        .count()
    )
    tailored = db.query(AIAnalysis).filter(AIAnalysis.tailored_resume != None).count()
    followups = sum((a.follow_up_count or 0) for a in db.query(Application).all())

    state = {
        "first_app":           total_applied >= 1,
        "ten_apps":            total_applied >= 10,
        "fifty_apps":          total_applied >= 50,
        "hundred_apps":        total_applied >= 100,
        "first_response":      responses >= 1,
        "first_interview":     interviews >= 1,
        "five_interviews":     interviews >= 5,
        "first_offer":         offers >= 1,
        "week_streak":         coding_streak >= 7,
        "month_streak":        coding_streak >= 30,
        "daily_player":        apply_streak >= 5,
        "ai_analyzed_50":      ai_analyzed >= 50,
        "ai_recommended_resume": tailored >= 1,
        "first_outreach":      outreach_count >= 1,
        "ten_outreach":        outreach_count >= 10,
        "three_resumes":       resume_count >= 3,
        "high_match_app":      high_match_apps >= 1,
        "follow_up_sent":      followups >= 1,
    }

    unlocked = []
    locked = []
    for badge in BADGES:
        if state.get(badge["id"], False):
            unlocked.append(badge)
        else:
            locked.append(badge)

    by_category = {}
    for badge in BADGES:
        cat = badge["category"]
        by_category.setdefault(cat, {"total": 0, "unlocked": 0})
        by_category[cat]["total"] += 1
        if state.get(badge["id"]):
            by_category[cat]["unlocked"] += 1

    level = _calculate_level(len(unlocked))

    return {
        "unlocked": unlocked,
        "locked": locked,
        "total_badges": len(BADGES),
        "unlocked_count": len(unlocked),
        "level": level,
        "by_category": by_category,
        "next_milestone": _next_milestone(state, total_applied, interviews),
    }


def _coding_streak(db) -> int:
    from database import CodingPractice
    practices = (
        db.query(CodingPractice)
        .filter(CodingPractice.completed == True)
        .order_by(CodingPractice.date.desc())
        .limit(60)
        .all()
    )
    if not practices:
        return 0
    today = datetime.utcnow().date()
    streak = 0
    cur = today
    for p in practices:
        try:
            p_date = datetime.fromisoformat(p.date).date()
        except Exception:
            continue
        if (cur - p_date).days <= 1:
            streak += 1
            cur = p_date
        else:
            break
    return streak


def _apply_streak(db) -> int:
    """Consecutive days with >=1 application sent."""
    from database import Job
    from collections import defaultdict
    apps = db.query(Job).filter(Job.applied_date != None).all()
    if not apps:
        return 0
    by_day = defaultdict(int)
    for j in apps:
        by_day[j.applied_date.date()] += 1
    today = datetime.utcnow().date()
    streak = 0
    cur = today
    while cur in by_day:
        streak += 1
        cur -= timedelta(days=1)
    return streak


def _calculate_level(unlocked_count: int) -> dict:
    levels = [
        (0, "Rookie"), (3, "Apprentice"), (6, "Climber"),
        (10, "Hunter"), (14, "Veteran"), (17, "Master"),
    ]
    level_num = 0
    name = "Rookie"
    for threshold, label in levels:
        if unlocked_count >= threshold:
            level_num = levels.index((threshold, label)) + 1
            name = label
    next_thresh = next((t for t, _ in levels if t > unlocked_count), len(BADGES))
    return {
        "number": level_num,
        "name": name,
        "badges_to_next": next_thresh - unlocked_count if next_thresh > unlocked_count else 0,
    }


def _next_milestone(state: dict, applied: int, interviews: int) -> str:
    if not state["first_app"]:
        return "Send your first application! (Jobs tab)"
    if not state["ten_apps"]:
        return f"Send {10 - applied} more applications to unlock 'Decimator' 🔟"
    if not state["first_interview"]:
        return "Get to interview stage — drives biggest probability bump"
    if not state["first_offer"]:
        return f"You have {interviews} interview(s). Convert one to land 'Job Hunter' 🏆"
    return "Keep optimizing! Apply for top-tier roles."
