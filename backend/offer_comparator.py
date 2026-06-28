"""
Offer comparison engine.
When you have 2+ offers, scores each across compensation, growth, culture,
location, and benefits. Gemini gives final recommendation with reasoning.
"""
import logging
import json

logger = logging.getLogger(__name__)


def save_offer(db, application_id: int, offer_data: dict) -> dict:
    """Store offer details in application record."""
    from database import Application
    app = db.query(Application).filter_by(id=application_id).first()
    if not app:
        return {"ok": False, "error": "Application not found"}
    app.offer_amount = json.dumps(offer_data)
    app.stage = "offer"
    db.commit()
    return {"ok": True, "application_id": application_id}


def list_offers(db) -> list:
    """List all applications in offer stage with structured offer data."""
    from database import Application, Job
    offers = db.query(Application).filter_by(stage="offer").all()
    result = []
    for app in offers:
        job = db.query(Job).filter_by(id=app.job_id).first()
        if not job:
            continue
        try:
            offer_data = json.loads(app.offer_amount) if app.offer_amount else {}
        except Exception:
            offer_data = {"base_salary": app.offer_amount or ""}
        result.append({
            "application_id": app.id,
            "job_id": job.id,
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "match_score": job.match_score,
            "offer": offer_data,
        })
    return result


def compare_offers(db, application_ids: list) -> dict:
    """Side-by-side comparison + Gemini recommendation."""
    from database import Application, Job
    from gemini import _run, PROFILE_SUMMARY

    if len(application_ids) < 2:
        return {"error": "Need at least 2 offers to compare"}

    offers = []
    for app_id in application_ids:
        app = db.query(Application).filter_by(id=app_id).first()
        if not app:
            continue
        job = db.query(Job).filter_by(id=app.job_id).first()
        if not job:
            continue
        try:
            data = json.loads(app.offer_amount) if app.offer_amount else {}
        except Exception:
            data = {}
        offers.append({
            "application_id": app.id,
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "data": data,
        })

    # Score each offer 0-100 on standard dimensions
    scored = []
    for o in offers:
        d = o["data"]
        base = int(str(d.get("base_salary", "0")).replace(",", "").replace("₹", "").replace("LPA", "").strip() or 0)
        if base < 200 and base > 0:
            base *= 100_000  # LPA to INR
        scores = {
            "compensation": min(round(base / 1_500_000 * 100), 100),
            "growth": int(d.get("growth_score", 50)),
            "culture": int(d.get("culture_score", 50)),
            "location_fit": 100 if any(t in (o["location"] or "").lower() for t in ["mumbai", "thane", "remote"]) else 30,
            "benefits": int(d.get("benefits_score", 50)),
        }
        weighted = round(
            scores["compensation"] * 0.35 +
            scores["growth"] * 0.25 +
            scores["culture"] * 0.15 +
            scores["location_fit"] * 0.15 +
            scores["benefits"] * 0.10
        )
        scored.append({**o, "scores": scores, "overall": weighted, "base_inr": base})

    # Gemini recommendation
    offers_str = "\n\n".join(
        f"Offer {i+1}: {o['title']} @ {o['company']} ({o['location']})\n"
        f"  Base: ₹{o['base_inr']:,}\n"
        f"  Overall score: {o['overall']}/100\n"
        f"  Details: {o['data']}"
        for i, o in enumerate(scored)
    )
    prompt = f"""Help this candidate choose between these job offers.

Candidate: {PROFILE_SUMMARY}

{offers_str}

Provide:
1. Your recommendation (which offer + 1-sentence why)
2. Top 2 reasons FOR the recommended one
3. Top 1 reason AGAINST it (be honest)
4. Negotiation suggestion for the chosen offer

Max 250 words. Direct, no fluff."""
    recommendation = _run(prompt, timeout=60)

    return {
        "offers": scored,
        "winner": max(scored, key=lambda x: x["overall"]) if scored else None,
        "ai_recommendation": recommendation,
    }
