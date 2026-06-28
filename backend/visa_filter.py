"""
Visa / work authorization filter.
Detects jobs that require US/UK work authorization, visa sponsorship,
or are open to candidates from India.
"""
import re

# Patterns suggesting the role needs US/UK auth (skip these for India candidates)
_VISA_REQUIRED = re.compile(
    r'\b(us\s+citizen|u\.s\.\s+citizen|green\s+card|h1b|tn\s+visa|'
    r'must\s+be\s+authorized|authorized\s+to\s+work\s+in\s+(?:the\s+)?us|'
    r'eligible\s+to\s+work\s+in\s+(?:the\s+)?us|'
    r'security\s+clearance|us\s+based\s+only)\b',
    re.IGNORECASE,
)

# Patterns suggesting visa sponsorship is offered (good for India candidates)
_SPONSORSHIP_OFFERED = re.compile(
    r'\b(visa\s+sponsorship|sponsorship\s+available|will\s+sponsor|'
    r'h1b\s+sponsorship|relocation\s+(?:assistance|support|provided))\b',
    re.IGNORECASE,
)

# Patterns suggesting open to international/India candidates
_INDIA_FRIENDLY = re.compile(
    r'\b(india|indian\s+candidates|remote\s+india|asia\s+pacific|apac|'
    r'global\s+remote|worldwide|any\s+location|remote\s+worldwide)\b',
    re.IGNORECASE,
)


def classify_visa(description: str, location: str) -> dict:
    text = (description or "") + " " + (location or "")
    requires_us_auth = bool(_VISA_REQUIRED.search(text))
    sponsorship = bool(_SPONSORSHIP_OFFERED.search(text))
    india_friendly = bool(_INDIA_FRIENDLY.search(text))

    loc_lower = (location or "").lower()
    is_india = any(t in loc_lower for t in ["india", "mumbai", "thane", "bangalore", "delhi", "pune", "hyderabad"])
    is_remote = any(t in loc_lower for t in ["remote", "anywhere", "worldwide"])

    if requires_us_auth and not sponsorship:
        accessibility = "blocked"
        reason = "Requires US/UK work authorization, no sponsorship offered"
    elif is_india or india_friendly:
        accessibility = "open"
        reason = "India-based or India-friendly"
    elif is_remote and not requires_us_auth:
        accessibility = "open"
        reason = "Remote, no location restriction"
    elif sponsorship:
        accessibility = "open"
        reason = "Sponsorship offered"
    else:
        accessibility = "unclear"
        reason = "Visa status not explicitly mentioned"

    return {
        "accessibility": accessibility,
        "reason": reason,
        "is_india_location": is_india,
        "is_remote": is_remote,
        "requires_visa": requires_us_auth and not sponsorship,
        "sponsorship_offered": sponsorship,
    }
