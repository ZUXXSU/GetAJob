import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))


def _csv(key: str, default: str = "") -> list:
    """Read comma-separated env var → list of lowercased stripped strings."""
    val = os.getenv(key, default)
    return [x.strip().lower() for x in val.split(",") if x.strip()]


def _csv_raw(key: str, default: str = "") -> list:
    """Like _csv but preserves case (for display values)."""
    val = os.getenv(key, default)
    return [x.strip() for x in val.split(",") if x.strip()]


# ── API Keys ───────────────────────────────────────────────────────────────────
ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID", "")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY", "")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")
HUNTER_API_KEY = os.getenv("HUNTER_API_KEY", "")

# ── Email / SMTP ───────────────────────────────────────────────────────────────
SMTP_EMAIL = os.getenv("SMTP_EMAIL", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
NOTIFY_EMAIL = os.getenv("NOTIFY_EMAIL", os.getenv("CANDIDATE_EMAIL", ""))

# ── LinkedIn ───────────────────────────────────────────────────────────────────
LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL", "")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD", "")

# ── Gemini CLI ─────────────────────────────────────────────────────────────────
GEMINI_BIN = os.getenv("GEMINI_BIN", "/usr/local/bin/gemini")

# ── Scheduler ──────────────────────────────────────────────────────────────────
SCRAPE_INTERVAL_HOURS = int(os.getenv("SCRAPE_INTERVAL_HOURS", "12"))
DIGEST_EMAIL_HOUR = int(os.getenv("DIGEST_EMAIL_HOUR", "9"))
AUTO_APPLY_ENABLED = os.getenv("AUTO_APPLY_ENABLED", "false").lower() == "true"
AUTO_APPLY_MIN_SCORE = int(os.getenv("AUTO_APPLY_MIN_SCORE", "85"))
AUTO_APPLY_INTERVAL_HOURS = int(os.getenv("AUTO_APPLY_INTERVAL_HOURS", "24"))

# ── Candidate Profile — all from .env, nothing hardcoded ──────────────────────
WEEKLY_REPORT_ENABLED = os.getenv("WEEKLY_REPORT_ENABLED", "true").lower() == "true"
WEEKLY_APPLY_GOAL = int(os.getenv("WEEKLY_APPLY_GOAL", "10"))
BLACKLIST_COMPANIES = _csv("BLACKLIST_COMPANIES", "")
BLACKLIST_KEYWORDS = _csv("BLACKLIST_KEYWORDS", "unpaid,commission only,mlm,network marketing")

PROFILE = {
    "name":             os.getenv("CANDIDATE_NAME", ""),
    "email":            os.getenv("CANDIDATE_EMAIL", ""),
    "phone":            os.getenv("CANDIDATE_PHONE", ""),
    "linkedin":         os.getenv("CANDIDATE_LINKEDIN", ""),
    "github":           os.getenv("CANDIDATE_GITHUB", ""),
    "location":         os.getenv("CANDIDATE_LOCATION", ""),
    "skills":           _csv("CANDIDATE_SKILLS",
                             "swift,kotlin,dart,javascript,python,java,"
                             "flutter,angular,react,reactjs,node,nodejs,"
                             "express,mysql,mongodb,postgresql,sqlite,postgres,"
                             "ios,android,mobile,saas,ui,ux,firebase,git,xcode,"
                             "android studio,rest api"),
    "target_roles":     _csv("CANDIDATE_TARGET_ROLES",
                             "ios developer,flutter developer,android developer,"
                             "mobile developer,mobile app developer,app developer,"
                             "full stack developer,fullstack developer,full-stack developer,"
                             "data analyst,ai engineer,software developer,"
                             "react native developer,cross platform developer"),
    "target_locations": _csv("CANDIDATE_LOCATION_TARGETS", "mumbai,thane,navi mumbai"),
    "accept_remote":    os.getenv("CANDIDATE_ACCEPT_REMOTE", "true").lower() == "true",
    "min_salary_inr":   int(os.getenv("CANDIDATE_MIN_SALARY_INR", "500000")),
    "experience_years": float(os.getenv("CANDIDATE_EXP_YEARS", "1.5")),
    "target_industries": _csv("CANDIDATE_TARGET_INDUSTRIES",
                              "ecommerce,health,social,entertainment,fintech,technology,saas,startup"),
    "search_queries":   _csv_raw("CANDIDATE_SEARCH_QUERIES",
                                 "flutter developer,ios developer swift,android developer kotlin,"
                                 "mobile developer,react native developer,"
                                 "full stack developer,software developer"),
}
