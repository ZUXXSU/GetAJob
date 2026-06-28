import re
from config import PROFILE
from experience_filter import extract_required_experience, experience_score_penalty, is_qualified


def score_job(title: str, description: str, location: str, salary_min: float = None) -> int:
    score = 0
    t = (title or "").lower()
    d = (description or "").lower()
    loc = (location or "").lower()

    # Role match in title (0–35 pts)
    if any(role in t for role in PROFILE["target_roles"]):
        score += 35
    elif any(role in d for role in PROFILE["target_roles"]):
        score += 15

    # Skills match (0–30 pts)
    hits = sum(1 for s in PROFILE["skills"] if s in d or s in t)
    score += min(hits * 3, 30)

    # Location (0–20 pts)
    if any(l in loc for l in PROFILE["target_locations"]):
        score += 20
    elif any(kw in loc for kw in ["remote", "work from home", "wfh"]):
        score += 15
    elif "india" in loc:
        score += 5

    # Salary (0–15 pts)
    if salary_min:
        if salary_min >= PROFILE["min_salary_inr"]:
            score += 15
        elif salary_min >= PROFILE["min_salary_inr"] * 0.8:
            score += 8

    # Experience requirement penalty
    req_exp = extract_required_experience(d)
    score += experience_score_penalty(req_exp)

    return max(0, min(int(score), 100))


def qualify_job(title: str, description: str) -> dict:
    """Full qualification check — returns dict with pass/fail + reasons."""
    d = (description or "").lower()
    t = (title or "").lower()
    req_exp = extract_required_experience(d)
    qualified = is_qualified(req_exp)
    role_match = any(role in t for role in PROFILE["target_roles"]) or \
                 any(role in d for role in PROFILE["target_roles"])
    skill_hits = [s for s in PROFILE["skills"] if s in d or s in t]
    return {
        "qualified": qualified and role_match,
        "role_match": role_match,
        "required_experience": req_exp,
        "experience_ok": qualified,
        "matched_skills": skill_hits,
        "skill_count": len(skill_hits),
    }


def parse_salary(text: str):
    """Return (min_inr, max_inr) from salary string, or (None, None)."""
    if not text:
        return None, None
    clean = text.replace(",", "").lower()
    nums = [float(n) for n in re.findall(r'\d+(?:\.\d+)?', clean)]
    if not nums:
        return None, None
    # Convert LPA → INR
    if "lpa" in clean or "lakh" in clean or ("l" in clean and max(nums) < 200):
        nums = [n * 100_000 for n in nums]
    elif max(nums) < 500:
        nums = [n * 1_000 for n in nums]
    if len(nums) == 1:
        return nums[0], nums[0]
    return min(nums[:2]), max(nums[:2])
