"""
Salary intelligence — aggregates salary data from all scraped jobs.
Computes percentiles per role/location. Gemini provides negotiation guidance.
"""
import logging
import statistics

logger = logging.getLogger(__name__)


def get_salary_intelligence(db, role_keyword: str = "", location_keyword: str = "") -> dict:
    """Aggregate salary stats from DB. Returns p25/p50/p75/p90 + count + advice."""
    from database import Job
    q = db.query(Job).filter(Job.salary_min != None, Job.salary_min > 0)
    if role_keyword:
        q = q.filter(Job.title.ilike(f"%{role_keyword}%"))
    if location_keyword:
        q = q.filter(Job.location.ilike(f"%{location_keyword}%"))

    jobs = q.all()
    salaries = [(j.salary_min or 0, j.salary_max or j.salary_min or 0) for j in jobs if (j.salary_min or 0) > 0]

    if not salaries:
        return {
            "sample_size": 0,
            "message": "Not enough salary data. Scrape more jobs.",
        }

    mins = [s[0] for s in salaries]
    maxs = [s[1] for s in salaries]

    def pct(data, p):
        sorted_data = sorted(data)
        if not sorted_data:
            return 0
        k = (len(sorted_data) - 1) * p
        f = int(k)
        c = min(f + 1, len(sorted_data) - 1)
        return sorted_data[f] + (sorted_data[c] - sorted_data[f]) * (k - f)

    p25 = pct(mins, 0.25)
    p50 = pct(mins, 0.50)
    p75 = pct(maxs, 0.75)
    p90 = pct(maxs, 0.90)

    # Gemini advice
    advice = ""
    try:
        from gemini import _run
        prompt = f"""Provide salary negotiation strategy based on these market stats.

Role: {role_keyword or 'Various'}
Location: {location_keyword or 'India'}
Sample size: {len(salaries)} jobs

Market percentiles (INR/year):
- 25th: ₹{int(p25):,}
- 50th (median): ₹{int(p50):,}
- 75th: ₹{int(p75):,}
- 90th: ₹{int(p90):,}

Candidate has 1.5 years experience.

Give 4 bullet points:
1. Realistic ask
2. Walk-away number
3. Non-salary benefits to negotiate
4. Phrasing for the salary conversation

Max 150 words."""
        advice = _run(prompt, timeout=30)
    except Exception as e:
        logger.warning(f"Salary advice failed: {e}")

    return {
        "sample_size": len(salaries),
        "role_filter": role_keyword or "all",
        "location_filter": location_keyword or "all",
        "p25_inr": int(p25),
        "p50_inr": int(p50),
        "p75_inr": int(p75),
        "p90_inr": int(p90),
        "min_seen": int(min(mins)) if mins else 0,
        "max_seen": int(max(maxs)) if maxs else 0,
        "mean_inr": int(statistics.mean(mins)) if mins else 0,
        "negotiation_advice": advice,
    }
