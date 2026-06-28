"""
Skill gap analyzer + learning recommendations.
Aggregates all AI analysis skill_gaps across applied/saved jobs.
Gemini suggests free resources to learn the missing skills.
"""
import json
import logging
from collections import Counter

logger = logging.getLogger(__name__)


def analyze_skill_gaps(db) -> dict:
    """
    Aggregate skill_gaps across all AI analyses.
    Returns the most-requested missing skills + Gemini learning roadmap.
    """
    from database import AIAnalysis

    analyses = db.query(AIAnalysis).filter(AIAnalysis.skill_gaps != None).all()
    gap_counter = Counter()
    for a in analyses:
        try:
            gaps = json.loads(a.skill_gaps) if a.skill_gaps else []
            for g in gaps:
                gap_counter[g.lower().strip()] += 1
        except Exception:
            continue

    top_gaps = gap_counter.most_common(10)
    if not top_gaps:
        return {
            "top_gaps": [],
            "learning_roadmap": "No skill gaps detected yet. Run AI analysis on more jobs.",
        }

    gap_list = "\n".join(f"- {skill} (appears in {count} jobs)" for skill, count in top_gaps)
    try:
        from gemini import _run, PROFILE_SUMMARY
        prompt = f"""Generate a 30-day learning roadmap for this candidate to close skill gaps.

Candidate: {PROFILE_SUMMARY}

Top skill gaps from job market analysis:
{gap_list}

Provide:
1. Top 3 skills to prioritize (with reasoning)
2. For each: 2-3 FREE learning resources (YouTube channels, docs, courses)
3. Practical project ideas to build for portfolio
4. Estimated time to job-ready proficiency

Keep under 300 words. Be specific. Real resource names only."""
        roadmap = _run(prompt, timeout=60)
    except Exception as e:
        roadmap = f"Top skills to learn: {', '.join(s for s,_ in top_gaps[:5])}"

    return {
        "top_gaps": [{"skill": s, "count": c} for s, c in top_gaps],
        "learning_roadmap": roadmap,
        "total_analyses": len(analyses),
    }
