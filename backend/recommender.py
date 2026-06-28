"""
Smart daily job recommendations.
Gemini picks the TOP 3 jobs to apply to TODAY from all high-score new jobs.
Considers: score, recency, variety of companies, experience match.
"""
import logging

logger = logging.getLogger(__name__)


def get_daily_top3(db) -> list:
    """
    Returns top 3 job dicts recommended by Gemini for today's applications.
    """
    from database import Job, AIAnalysis
    # Get all high-score new jobs, not yet applied
    candidates = (
        db.query(Job)
        .filter(Job.match_score >= 70, Job.status == "new")
        .order_by(Job.match_score.desc())
        .limit(30)
        .all()
    )
    if not candidates:
        return []
    if len(candidates) <= 3:
        return [_job_summary(j) for j in candidates]

    # Build list for Gemini
    job_list = "\n".join(
        f"{i+1}. [{j.id}] {j.title} @ {j.company} | {j.location} | score={j.match_score} | {j.salary_text or 'salary N/A'}"
        for i, j in enumerate(candidates[:20])
    )

    try:
        from gemini import _run, PROFILE_SUMMARY
        prompt = f"""You are a career advisor. Pick the TOP 3 jobs to apply to TODAY.

Candidate: {PROFILE_SUMMARY}

Available jobs (sorted by match score):
{job_list}

Selection criteria:
- Highest match score
- Company variety (don't pick 3 from same company)
- Location preference (Mumbai/Thane/remote over others)
- Realistic experience fit

Respond ONLY with the 3 job numbers separated by commas. Example: 1,5,12"""
        raw = _run(prompt, timeout=30)
        import re
        nums = [int(n) - 1 for n in re.findall(r'\d+', raw) if 0 < int(n) <= len(candidates)][:3]
        if nums:
            return [_job_summary(candidates[i]) for i in nums if i < len(candidates)]
    except Exception as e:
        logger.warning(f"Gemini recommendation failed: {e}")

    # Fallback: top 3 by score
    return [_job_summary(j) for j in candidates[:3]]


def _job_summary(j) -> dict:
    return {
        "id": j.id,
        "title": j.title,
        "company": j.company,
        "location": j.location,
        "score": j.match_score,
        "salary": j.salary_text or "",
        "url": j.url,
        "source": j.source,
    }


def cleanup_old_jobs(db, days: int = 60) -> int:
    """Remove jobs older than `days` days with status 'new' and score < 50. Returns count deleted."""
    from datetime import datetime, timedelta
    from database import Job
    cutoff = datetime.utcnow() - timedelta(days=days)
    old = (
        db.query(Job)
        .filter(Job.found_date < cutoff, Job.status == "new", Job.match_score < 50)
        .all()
    )
    count = len(old)
    for j in old:
        db.delete(j)
    db.commit()
    logger.info(f"Cleaned {count} old low-score jobs (older than {days} days)")
    return count
