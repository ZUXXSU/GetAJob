"""
Coding practice tracker — daily problem-solving for interview prep.
Tracks streak, suggests problems based on target role.
Gemini picks one problem per day from common interview topics.
"""
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

_TOPICS = [
    "Arrays & Strings",
    "Linked Lists",
    "Stacks & Queues",
    "Trees & Graphs",
    "Hash Maps",
    "Dynamic Programming",
    "Sliding Window",
    "Two Pointers",
    "Binary Search",
    "Sorting",
    "Recursion & Backtracking",
    "Greedy",
    "Bit Manipulation",
]


def get_daily_problem(db, target_role: str = "Mobile Developer") -> dict:
    """Get today's coding problem suggestion."""
    from database import CodingPractice

    today = datetime.utcnow().date().isoformat()
    existing = db.query(CodingPractice).filter_by(date=today).first()
    if existing:
        return {
            "date": today,
            "topic": existing.topic,
            "problem": existing.problem_title,
            "platform_url": existing.platform_url,
            "completed": existing.completed,
            "difficulty": existing.difficulty,
            "cached": True,
        }

    # Pick topic by rotating through list based on day-of-year
    day_of_year = datetime.utcnow().timetuple().tm_yday
    topic = _TOPICS[day_of_year % len(_TOPICS)]

    try:
        from gemini import _run
        prompt = f"""Suggest ONE coding interview problem for today's practice.

Topic: {topic}
Target role: {target_role}
Day-of-year: {day_of_year} (use to vary problem)

Return as JSON only:
{{"title": "Problem name", "difficulty": "Easy|Medium|Hard", "url": "leetcode.com/problems/...", "reason": "1 sentence why this matters for the role"}}"""
        import json
        import re
        raw = _run(prompt, timeout=30)
        raw = re.sub(r"```json\n?|```\n?", "", raw).strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            problem_title = data.get("title", "Two Sum")
            platform_url = data.get("url", "https://leetcode.com")
            difficulty = data.get("difficulty", "Easy")
        else:
            problem_title = f"{topic} practice"
            platform_url = "https://leetcode.com/problemset/all/"
            difficulty = "Medium"
    except Exception as e:
        logger.warning(f"Gemini practice problem failed: {e}")
        problem_title = f"{topic} practice"
        platform_url = "https://leetcode.com/problemset/all/"
        difficulty = "Medium"

    p = CodingPractice(
        date=today,
        topic=topic,
        problem_title=problem_title,
        platform_url=platform_url,
        difficulty=difficulty,
        completed=False,
    )
    db.add(p)
    db.commit()
    return {
        "date": today,
        "topic": topic,
        "problem": problem_title,
        "platform_url": platform_url,
        "difficulty": difficulty,
        "completed": False,
        "cached": False,
    }


def mark_completed(db, date_str: str) -> dict:
    from database import CodingPractice
    p = db.query(CodingPractice).filter_by(date=date_str).first()
    if not p:
        return {"ok": False, "error": "No practice for that date"}
    p.completed = True
    p.completed_at = datetime.utcnow()
    db.commit()
    return {"ok": True}


def get_streak(db) -> dict:
    """Calculate current coding practice streak."""
    from database import CodingPractice
    practices = (
        db.query(CodingPractice)
        .filter(CodingPractice.completed == True)
        .order_by(CodingPractice.date.desc())
        .all()
    )
    if not practices:
        return {"streak": 0, "total_solved": 0, "last_solved": None}

    today = datetime.utcnow().date()
    streak = 0
    cur = today
    for p in practices:
        try:
            p_date = datetime.fromisoformat(p.date).date() if isinstance(p.date, str) else p.date
        except Exception:
            continue
        if (cur - p_date).days <= 1:
            streak += 1
            cur = p_date
        else:
            break

    return {
        "streak": streak,
        "total_solved": len(practices),
        "last_solved": practices[0].date if practices else None,
    }
