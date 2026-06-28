"""
Experience requirement extractor and qualifier.
Checks if a job's experience requirement matches Hardik's ~2 years.
"""
import re
from typing import Optional

from config import PROFILE

_CANDIDATE_EXP_YEARS = PROFILE.get("experience_years", 1.5)
_MAX_ACCEPTABLE_EXP = 3.0  # Jobs requiring > 3 years get penalized

_FRESHER_RE = re.compile(r'fresher|entry.level|0[-–]1\s+year|no\s+experience\s+required', re.IGNORECASE)

# Finds "5+ years", "3-5 years", "minimum 2 years" — captures the lower bound
_YEAR_PATTERNS = [
    (r'(\d+)\s*\+\s*years?', lambda m: int(m.group(1))),           # 5+ years
    (r'(\d+)\s*[-–]\s*\d+\s*years?', lambda m: int(m.group(1))),   # 3-5 years → 3
    (r'minimum\s+(?:of\s+)?(\d+)\s+years?', lambda m: int(m.group(1))),
    (r'at\s+least\s+(\d+)\s+years?', lambda m: int(m.group(1))),
    (r'(\d+)\s+years?\s+(?:of\s+)?(?:\w+\s+){0,4}(?:experience|exp)', lambda m: int(m.group(1))),
    (r'(?:experience|exp)[\s:of]+(\d+)\s+years?', lambda m: int(m.group(1))),
]


def extract_required_experience(description: str) -> Optional[int]:
    """Return minimum required years from job description. None if not specified."""
    if not description:
        return None
    text = description.lower()

    # Fresher/entry level
    if _FRESHER_RE.search(text):
        return 0

    # Only look in sentences that mention experience
    exp_context = []
    for sentence in re.split(r'[.;\n]', text):
        if 'year' in sentence or 'experience' in sentence or 'exp' in sentence:
            exp_context.append(sentence)
    search_text = ' '.join(exp_context) if exp_context else text

    found = []
    for pattern, extractor in _YEAR_PATTERNS:
        for m in re.finditer(pattern, search_text):
            try:
                val = extractor(m)
                if 0 < val <= 20:  # sanity: 1–20 years
                    found.append(val)
            except Exception:
                pass
    if not found:
        return None
    return min(found)


def is_qualified(required_years: Optional[int]) -> bool:
    """True if candidate meets the experience requirement."""
    if required_years is None:
        return True
    return _CANDIDATE_EXP_YEARS >= required_years * 0.75  # 25% buffer


def experience_score_penalty(required_years: Optional[int]) -> int:
    """Score penalty (negative) for experience mismatch. 0 if qualified."""
    if required_years is None or required_years == 0:
        return 0
    if _CANDIDATE_EXP_YEARS >= required_years:
        return 0
    gap = required_years - _CANDIDATE_EXP_YEARS
    if gap <= 1:
        return -10   # 1 yr gap: minor penalty
    elif gap <= 2:
        return -25   # 2 yr gap: moderate
    elif gap <= 3:
        return -40   # 3 yr gap: significant
    return -60       # 4+ yr gap: major


def experience_label(required_years: Optional[int]) -> str:
    if required_years is None:
        return "Exp: Not specified"
    if required_years == 0:
        return "Exp: Fresher/Entry"
    qualified = is_qualified(required_years)
    symbol = "✓" if qualified else "⚠"
    return f"Exp: {required_years}+ yr required {symbol}"
