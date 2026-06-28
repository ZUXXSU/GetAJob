"""
Daily Job Search Playbook.
Returns a structured 2-hour/day routine — what to do RIGHT NOW.
Combines: success predictor's top actions + time-blocked schedule + checkboxes.

The "operating system" for the job search. Each task is concrete and timed.
"""
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def get_daily_playbook(db) -> dict:
    """Returns today's playbook — 6 time-blocked tasks (~2 hours total)."""
    from success_predictor import predict_success
    from coding_practice import get_daily_problem
    from database import Job, Application
    from datetime import timedelta

    pred = predict_success(db, target_days=90)
    components = pred["components"]
    metrics = pred["metrics"]

    # Today's coding problem
    problem = get_daily_problem(db)

    # Pending follow-ups due today
    now = datetime.utcnow()
    week_threshold = now - timedelta(days=7)
    pending_followups = (
        db.query(Application)
        .filter(
            Application.email_sent == True,
            Application.response_received == False,
            Application.email_sent_at < week_threshold,
            Application.follow_up_count < 2,
        )
        .count()
    )

    # High-match jobs ready to apply
    ready_jobs = (
        db.query(Job)
        .filter(Job.match_score >= 80, Job.status == "new", Job.auto_applied == False)
        .count()
    )

    tasks = []

    # ── BLOCK 1: Morning — Apply (30 min) ──
    apply_target = max(0, 3 - metrics["applied_last_7"] // 2)
    if ready_jobs > 0:
        tasks.append({
            "block": "Morning",
            "time": "8:00 AM – 8:30 AM",
            "duration_min": 30,
            "task": f"Apply to {min(apply_target or 3, ready_jobs)} high-match jobs",
            "why": f"You have {ready_jobs} jobs scoring 80+. Each application = 5% probability bump.",
            "action_url": "/?tab=jobs&min_score=80",
            "icon": "📨",
            "priority": "high",
            "done": False,
        })

    # ── BLOCK 2: Coding (45 min) ──
    if not problem.get("completed"):
        tasks.append({
            "block": "Morning",
            "time": "8:30 AM – 9:15 AM",
            "duration_min": 45,
            "task": f"Solve today's problem: {problem['problem']}",
            "why": f"{problem['topic']} ({problem['difficulty']}). Interview readiness: {components['interview_readiness']}/100",
            "action_url": problem["platform_url"],
            "icon": "💻",
            "priority": "high",
            "done": False,
        })

    # ── BLOCK 3: Outreach (20 min) ──
    if components["network"] < 70:
        tasks.append({
            "block": "Morning",
            "time": "9:15 AM – 9:35 AM",
            "duration_min": 20,
            "task": "Send 2 cold LinkedIn messages",
            "why": "70% of jobs come through networking. Network score: " + str(components["network"]) + "/100",
            "action_url": "/?tab=coach#outreach",
            "icon": "🤝",
            "priority": "high",
            "done": False,
        })

    # ── BLOCK 4: Follow-ups (10 min) ──
    if pending_followups > 0:
        tasks.append({
            "block": "Afternoon",
            "time": "2:00 PM – 2:10 PM",
            "duration_min": 10,
            "task": f"Send {pending_followups} pending follow-up email(s)",
            "why": "Follow-ups 2× response rates. Best sent in afternoon.",
            "action_url": "/?tab=followups",
            "icon": "📧",
            "priority": "medium",
            "done": False,
        })

    # ── BLOCK 5: Review AI analysis (15 min) ──
    if components["ai_coverage"] < 80:
        tasks.append({
            "block": "Afternoon",
            "time": "2:10 PM – 2:25 PM",
            "duration_min": 15,
            "task": "Run AI analysis on unanalyzed jobs",
            "why": f"Only {components['ai_coverage']}% of jobs analyzed. AI filters out wrong-fit roles.",
            "action_url": "/?tab=dashboard",
            "icon": "🤖",
            "priority": "medium",
            "done": False,
        })

    # ── BLOCK 6: Mock interview (15 min, only if interviews in pipeline) ──
    if metrics["interviews"] > 0:
        tasks.append({
            "block": "Evening",
            "time": "7:00 PM – 7:15 PM",
            "duration_min": 15,
            "task": "Practice 1 mock interview question with Gemini",
            "why": f"{metrics['interviews']} interviews scheduled. Practice = better performance.",
            "action_url": "/?tab=coach#mock",
            "icon": "🎤",
            "priority": "high",
            "done": False,
        })

    # Total time
    total_min = sum(t["duration_min"] for t in tasks)

    # Today's success boost potential
    potential_boost = 0
    for t in tasks:
        if t["priority"] == "high":
            potential_boost += 8
        elif t["priority"] == "medium":
            potential_boost += 5
        else:
            potential_boost += 3

    return {
        "date": datetime.utcnow().date().isoformat(),
        "current_probability": pred["probability_pct"],
        "potential_after_completion": min(pred["probability_pct"] + potential_boost, 95),
        "total_time_min": total_min,
        "task_count": len(tasks),
        "tasks": tasks,
        "motivational_message": _get_message(pred["probability_pct"], len(tasks)),
    }


def _get_message(prob: int, task_count: int) -> str:
    if prob >= 70:
        return "💪 You're crushing it. Stay consistent."
    elif prob >= 40:
        return "📈 Strong trajectory. Today's tasks lock in your momentum."
    elif prob >= 20:
        return f"⚡ Every action counts. {task_count} tasks today → measurable progress."
    else:
        return "🚀 Day 1 mindset. The compound starts NOW. Do the first task."
