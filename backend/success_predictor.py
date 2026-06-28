"""
Job Search Success Predictor.
Quantifies your probability of landing a job within N days.
Combines: application velocity, response rate, pipeline health, skill match,
network activity, resume strength, and coding practice consistency.

Outputs concrete actions to maximize the probability — closest software can get to "guarantee".
"""
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def predict_success(db, target_days: int = 90) -> dict:
    """
    Returns probability score (0-100) + 5 specific actions to improve it.
    """
    from database import Application, Job, AIAnalysis, ResumeProfile, CodingPractice, OutreachLog

    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    # ── Metrics ──
    total_jobs = db.query(Job).count()
    high_match = db.query(Job).filter(Job.match_score >= 80).count()
    applied_last_30 = db.query(Job).filter(Job.applied_date >= month_ago).count()
    applied_last_7 = db.query(Job).filter(Job.applied_date >= week_ago).count()
    total_applied = db.query(Job).filter(Job.status == "applied").count()
    interviews = db.query(Application).filter(Application.stage == "interview").count()
    offers = db.query(Application).filter(Application.stage == "offer").count()
    responses = db.query(Application).filter(Application.response_received == True).count()
    ai_analyzed = db.query(AIAnalysis).count()
    resume_count = db.query(ResumeProfile).count()
    coding_streak = _coding_streak(db)
    outreach_sent = db.query(OutreachLog).count()

    # ── Component scores (0-100 each) ──
    components = {}

    # 1. Application velocity (target: 10/week = 100)
    components["velocity"] = min(applied_last_7 * 10, 100)

    # 2. Pipeline health (interviews + offers)
    if total_applied == 0:
        components["pipeline"] = 0
    else:
        components["pipeline"] = min(round((interviews * 30 + offers * 50) / max(total_applied, 1)), 100)

    # 3. Response rate (target: 15% = 100)
    if total_applied == 0:
        components["response_rate"] = 0
    else:
        rr = responses / max(total_applied, 1)
        components["response_rate"] = min(round(rr * 666), 100)  # 15% = 100

    # 4. High-match job pool (target: 20 = 100)
    components["pool_health"] = min(round(high_match * 5), 100)

    # 5. AI optimization coverage (target: all jobs analyzed)
    components["ai_coverage"] = min(round(ai_analyzed / max(total_jobs, 1) * 100), 100)

    # 6. Resume readiness (target: 3+ resumes for variety)
    components["resume_variety"] = min(round(resume_count * 33), 100)

    # 7. Coding/interview prep (target: 7-day streak = 100)
    components["interview_readiness"] = min(coding_streak * 14, 100)

    # 8. Network outreach (target: 20+ outreach msgs)
    components["network"] = min(round(outreach_sent * 5), 100)

    # ── Weighted overall score ──
    weights = {
        "velocity": 0.20,        # actions taken matter most
        "pipeline": 0.20,        # deep results matter
        "response_rate": 0.15,
        "pool_health": 0.10,
        "ai_coverage": 0.10,
        "resume_variety": 0.05,
        "interview_readiness": 0.10,
        "network": 0.10,
    }
    overall = round(sum(components[k] * w for k, w in weights.items()))

    # ── Probability calculation ──
    # Base curve: probability of offer within target_days
    # Empirical model: 30 high-quality apps + 1 interview + 1 offer = ~70% in 90 days
    if total_applied >= 30 and interviews >= 1:
        base_prob = min(60 + overall * 0.4, 95)
    elif total_applied >= 20:
        base_prob = min(40 + overall * 0.5, 85)
    elif total_applied >= 10:
        base_prob = min(25 + overall * 0.5, 70)
    elif total_applied >= 1:
        base_prob = min(15 + overall * 0.4, 50)
    else:
        base_prob = max(5, overall * 0.2)

    # ── Top 5 actions, prioritized by weight × deficit ──
    actions = _prioritized_actions(components, applied_last_7, high_match,
                                    ai_analyzed, total_jobs, interviews,
                                    coding_streak, resume_count, outreach_sent)

    return {
        "overall_score": overall,
        "probability_pct": round(base_prob),
        "target_days": target_days,
        "interpretation": _interpret(base_prob),
        "components": components,
        "metrics": {
            "total_jobs": total_jobs,
            "high_match_available": high_match,
            "applied_last_7": applied_last_7,
            "applied_last_30": applied_last_30,
            "total_applied": total_applied,
            "interviews": interviews,
            "offers": offers,
            "responses": responses,
            "coding_streak_days": coding_streak,
            "resume_count": resume_count,
            "outreach_sent": outreach_sent,
        },
        "top_actions": actions,
    }


def _coding_streak(db) -> int:
    from database import CodingPractice
    practices = (
        db.query(CodingPractice)
        .filter(CodingPractice.completed == True)
        .order_by(CodingPractice.date.desc())
        .limit(30)
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


def _prioritized_actions(c: dict, applied_7, high_match, ai_analyzed, total_jobs,
                         interviews, coding_streak, resume_count, outreach_sent) -> list:
    actions = []

    if c["velocity"] < 80:
        deficit = 100 - c["velocity"]
        need = max(10 - applied_7, 1)
        actions.append({
            "priority": deficit * 0.20,
            "title": f"Apply to {need} more jobs this week",
            "why": "Application volume is the #1 predictor. 10/week is the proven threshold.",
            "how": f"Open the Coach tab → Today's Top 3 picks → apply now. Currently applied {applied_7}/10.",
        })

    if c["pipeline"] < 60 and applied_7 < 10:
        actions.append({
            "priority": 70,
            "title": "Build pipeline before optimizing",
            "why": f"Only {interviews} interviews in pipeline. Need volume first.",
            "how": "Apply to 30+ jobs before worrying about response rate. Use Auto-Apply on 80+ score matches.",
        })

    if c["ai_coverage"] < 50:
        actions.append({
            "priority": deficit_calc(c["ai_coverage"]) * 0.10,
            "title": "Run AI analysis on all jobs",
            "why": f"Only {ai_analyzed}/{total_jobs} jobs analyzed. AI filters out wrong-fit jobs.",
            "how": "Dashboard → ✨ Analyze All button (top right).",
        })

    if c["network"] < 50 and outreach_sent < 10:
        actions.append({
            "priority": 60,
            "title": "Send 5 cold outreach messages this week",
            "why": "70% of jobs come through networking, not applications.",
            "how": "Coach tab → Cold Outreach Templates → personalize 5 → send via LinkedIn.",
        })

    if c["interview_readiness"] < 40:
        actions.append({
            "priority": 55,
            "title": "Start daily coding practice today",
            "why": f"Coding streak: {coding_streak} days. Interview success depends on practice.",
            "how": "Coach tab → Daily Coding Practice → solve today's problem.",
        })

    if c["resume_variety"] < 60 and resume_count < 3:
        actions.append({
            "priority": 45,
            "title": "Create role-specific resume variants",
            "why": f"Only {resume_count} resume(s) saved. Tailoring increases response rate 3×.",
            "how": "Resumes tab → + Add Resume → make one each for Flutter, Full Stack, iOS.",
        })

    if c["pool_health"] < 40:
        actions.append({
            "priority": 40,
            "title": "Trigger fresh scrape",
            "why": f"Only {high_match} high-match jobs available. Pipeline running low.",
            "how": "Dashboard → Scrape button (top right). Or wait — auto-scrapes every 12h.",
        })

    if c["response_rate"] < 30 and applied_7 >= 5:
        actions.append({
            "priority": 50,
            "title": "Optimize resume for ATS",
            "why": "Low response rate suggests resume isn't passing automated filters.",
            "how": "Open any high-score job → ATS Check button → add missing keywords.",
        })

    actions.sort(key=lambda x: x["priority"], reverse=True)
    return actions[:5]


def deficit_calc(score: int) -> int:
    return 100 - score


def _interpret(prob: float) -> str:
    if prob >= 80:
        return "🎯 Very high. Stay consistent — offer is highly likely."
    elif prob >= 60:
        return "✅ Strong. Maintain velocity and the offer will follow."
    elif prob >= 40:
        return "📈 Building. Execute the top actions to accelerate."
    elif prob >= 20:
        return "⚠️ Early. Focus on volume and pipeline before optimization."
    else:
        return "🚀 Just starting. First action: apply to 5 jobs today."
