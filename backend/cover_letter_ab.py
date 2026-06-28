"""
Cover letter A/B testing.
Tracks which cover letter "style" gets the most responses.
Tags every generated letter with a variant (formal/casual/data-driven/story).
Computes response rate per variant — auto-prefers winning style.
"""
import logging
import random

logger = logging.getLogger(__name__)


COVER_LETTER_VARIANTS = {
    "formal": {
        "name": "Formal Professional",
        "instructions": "Use formal business English. Lead with credentials and degree. "
                        "Third paragraph closes with respectful call to action.",
    },
    "casual": {
        "name": "Casual Conversational",
        "instructions": "Write conversationally like you're talking to a colleague. "
                        "Lead with a hook about why this role excites you. Keep it warm.",
    },
    "data_driven": {
        "name": "Data-Driven Achievements",
        "instructions": "Lead with quantified achievements (numbers, metrics, percentages). "
                        "Every paragraph should reference a concrete result.",
    },
    "story": {
        "name": "Story-First",
        "instructions": "Open with a brief story or problem you solved. "
                        "Show personality. End with what excites you about this team.",
    },
}


def pick_variant(db) -> str:
    """
    Pick a variant for the next cover letter.
    Uses Thompson-like sampling: 70% pick winning, 30% explore others.
    """
    from database import AIAnalysis, Application

    # Calculate response rate per variant
    stats = get_variant_stats(db)

    if not stats or all(s["sent"] < 3 for s in stats.values()):
        # Not enough data — round-robin to explore
        return random.choice(list(COVER_LETTER_VARIANTS.keys()))

    # 30% explore: pick random
    if random.random() < 0.3:
        return random.choice(list(COVER_LETTER_VARIANTS.keys()))

    # 70% exploit: pick best response rate among variants with >= 3 sent
    qualified = {k: v for k, v in stats.items() if v["sent"] >= 3}
    if not qualified:
        return random.choice(list(COVER_LETTER_VARIANTS.keys()))
    best = max(qualified.items(), key=lambda x: x[1]["response_rate"])
    return best[0]


def get_variant_instructions(variant: str) -> str:
    return COVER_LETTER_VARIANTS.get(variant, COVER_LETTER_VARIANTS["formal"])["instructions"]


def get_variant_stats(db) -> dict:
    """Compute sent + response counts per variant."""
    from database import AIAnalysis, Application

    # Use applications joined with cover letter variant tags
    apps = db.query(Application).filter(Application.email_sent == True).all()
    stats = {k: {"sent": 0, "responses": 0} for k in COVER_LETTER_VARIANTS.keys()}

    for app in apps:
        analysis = db.query(AIAnalysis).filter_by(job_id=app.job_id).first()
        if not analysis:
            continue
        # Variant tag stored in cover letter as a special marker (first line)
        cl = analysis.cover_letter or ""
        variant = _extract_variant_tag(cl)
        if variant in stats:
            stats[variant]["sent"] += 1
            if app.response_received:
                stats[variant]["responses"] += 1

    for k, v in stats.items():
        v["response_rate"] = (
            round(v["responses"] / v["sent"] * 100, 1) if v["sent"] > 0 else 0
        )
        v["name"] = COVER_LETTER_VARIANTS[k]["name"]

    return stats


def _extract_variant_tag(cover_letter: str) -> str:
    """Variants tagged in first line: '<!-- variant: data_driven -->'"""
    if not cover_letter:
        return "formal"
    first_line = cover_letter.split("\n")[0]
    if "variant:" in first_line:
        for v in COVER_LETTER_VARIANTS.keys():
            if v in first_line:
                return v
    return "formal"


def tag_letter(cover_letter: str, variant: str) -> str:
    """Add hidden variant marker to cover letter."""
    return f"<!-- variant: {variant} -->\n{cover_letter}"


def strip_tag(cover_letter: str) -> str:
    """Remove variant tag for outgoing email."""
    if cover_letter.startswith("<!--"):
        lines = cover_letter.split("\n", 1)
        return lines[1] if len(lines) > 1 else cover_letter
    return cover_letter
