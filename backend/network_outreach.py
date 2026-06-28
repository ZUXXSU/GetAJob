"""
Network outreach suggestions.
Gemini generates targeted networking actions: who to contact, what to say.
Useful for the 'hidden job market' beyond formal applications.
"""
import logging

logger = logging.getLogger(__name__)


def get_outreach_suggestions(db) -> dict:
    """Generate weekly network outreach plan."""
    from database import Application, Job

    # Find unique companies applied to
    applied_companies = {
        j.company for j in db.query(Job).filter(Job.status == "applied").all() if j.company
    }

    # Top target companies from high-score jobs
    top_jobs = (
        db.query(Job)
        .filter(Job.match_score >= 75, Job.status == "new")
        .order_by(Job.match_score.desc())
        .limit(10)
        .all()
    )
    target_companies = list({j.company for j in top_jobs if j.company})[:5]

    try:
        from gemini import _run, PROFILE_SUMMARY
        prompt = f"""Generate a 1-week networking outreach plan for this candidate.

Candidate: {PROFILE_SUMMARY}

Companies they want to apply to next week (high score):
{', '.join(target_companies) if target_companies else 'No specific targets yet'}

Generate 5 concrete networking actions for this week:
1. WHO to contact (role/title at which company, where to find them)
2. WHAT channel (LinkedIn, Twitter, Discord communities, alumni network)
3. WHAT to say (short message template, max 2 sentences each)

Format as numbered list. Focus on actions that lead to referrals or warm intros.
Max 250 words. Be specific and concrete."""
        actions = _run(prompt, timeout=45)
    except Exception:
        actions = "Connect with engineers at your target companies on LinkedIn. Ask one specific question about their work."

    return {
        "target_companies": target_companies,
        "applied_companies_count": len(applied_companies),
        "outreach_actions": actions,
        "tip": "Networking yields 70% of all jobs. Spend 30 min/day on outreach for fastest results.",
    }
