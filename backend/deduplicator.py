"""
Cross-source job deduplication.
Prevents same job from being stored multiple times when it appears on
Adzuna + Naukri + LinkedIn simultaneously.
"""
import re
from difflib import SequenceMatcher


def _normalize(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9 ]', '', text.lower())).strip()


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


def is_duplicate(title: str, company: str, db) -> bool:
    """
    Check if a job with similar title+company already exists in DB.
    Uses fuzzy match (>= 0.85 similarity) to catch minor variations.
    """
    from database import Job
    # Fast exact check first
    norm_company = _normalize(company)
    candidates = (
        db.query(Job)
        .filter(Job.company.ilike(f"%{company[:15]}%"))
        .limit(50)
        .all()
    )
    for j in candidates:
        if (similarity(j.title or "", title) >= 0.85 and
                similarity(j.company or "", company) >= 0.80):
            return True
    return False


def find_best_source(title: str, company: str, db) -> str:
    """Return the source of the existing duplicate, or empty string."""
    from database import Job
    norm_company = _normalize(company)
    candidates = (
        db.query(Job)
        .filter(Job.company.ilike(f"%{company[:15]}%"))
        .limit(50)
        .all()
    )
    for j in candidates:
        if (similarity(j.title or "", title) >= 0.85 and
                similarity(j.company or "", company) >= 0.80):
            return j.source or ""
    return ""
