"""
HR contact finder — extracts or guesses HR emails for auto-apply.
Priority: 1) regex from description 2) Hunter.io 3) Gemini guess 4) domain guess
"""
import logging
import re
import urllib.parse

import requests

from config import HUNTER_API_KEY
from gemini import find_hr_email

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", re.IGNORECASE)
_SKIP_DOMAINS = {"example.com", "gmail.com", "yahoo.com", "naukri.com",
                 "linkedin.com", "adzuna.com", "remotive.com", "jsearch.com"}


def extract_domain(url: str) -> str:
    try:
        return urllib.parse.urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def find_contact(company: str, job_url: str, description: str) -> str:
    """Return best HR email for this company. Empty string if unknown."""
    # 1. Regex from description
    emails = _EMAIL_RE.findall(description or "")
    valid = [e for e in emails if e.split("@")[1] not in _SKIP_DOMAINS]
    if valid:
        logger.info(f"Email found in description: {valid[0]}")
        return valid[0]

    domain = extract_domain(job_url)

    # 2. Hunter.io
    if HUNTER_API_KEY and domain:
        email = _hunter_find(company, domain)
        if email:
            logger.info(f"Email from Hunter.io: {email}")
            return email

    # 3. Gemini guess
    if company:
        email = find_hr_email(company, domain, description or "")
        if email and "@" in email:
            logger.info(f"Email from Gemini: {email}")
            return email

    # 4. Domain guess
    if domain and domain not in _SKIP_DOMAINS:
        guessed = f"careers@{domain}"
        logger.info(f"Guessed email: {guessed}")
        return guessed

    return ""


def _hunter_find(company: str, domain: str) -> str:
    try:
        r = requests.get(
            "https://api.hunter.io/v2/domain-search",
            params={"domain": domain, "company": company, "api_key": HUNTER_API_KEY, "limit": 3},
            timeout=10,
        )
        data = r.json().get("data", {})
        emails = data.get("emails", [])
        # Prefer HR/talent/recruiter emails
        hr_keywords = ["hr", "talent", "recruit", "career", "people"]
        for kw in hr_keywords:
            for e in emails:
                if kw in e.get("value", "").lower() or kw in e.get("position", "").lower():
                    return e["value"]
        if emails:
            return emails[0]["value"]
    except Exception as e:
        logger.debug(f"Hunter.io error: {e}")
    return ""
