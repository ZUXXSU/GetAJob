"""
First-time user onboarding wizard state.
Tracks completion of essential setup steps. Returns what's left to configure.
"""
import logging
import os

logger = logging.getLogger(__name__)


def get_onboarding_status(db) -> dict:
    """Check setup completeness; return checklist with next-step guidance."""
    from config import (PROFILE, SMTP_EMAIL, SMTP_PASSWORD, ADZUNA_APP_ID,
                        RAPIDAPI_KEY, AUTO_APPLY_ENABLED, LINKEDIN_EMAIL,
                        WEEKLY_APPLY_GOAL)
    from database import ResumeProfile, Job, Application

    checks = []

    # 1. Profile filled
    profile_complete = bool(
        PROFILE.get("name") and PROFILE.get("email") and PROFILE.get("phone") and
        PROFILE.get("skills") and PROFILE.get("target_roles")
    )
    checks.append({
        "step": "1. Personal Profile",
        "done": profile_complete,
        "action": "Edit .env with CANDIDATE_* variables" if not profile_complete else "Complete",
        "doc": "See README.md → Configuration → Personal Profile",
    })

    # 2. SMTP configured
    smtp_ok = bool(SMTP_EMAIL and SMTP_PASSWORD)
    checks.append({
        "step": "2. Email Sending (Gmail)",
        "done": smtp_ok,
        "action": "Add SMTP_EMAIL + SMTP_PASSWORD (Gmail App Password) to .env" if not smtp_ok else "Complete",
        "doc": "https://myaccount.google.com/apppasswords",
    })

    # 3. At least one job source
    has_source = bool(ADZUNA_APP_ID or RAPIDAPI_KEY)
    checks.append({
        "step": "3. API Job Sources",
        "done": True,  # We have LinkedIn + Naukri + Remotive + RemoteOK without keys
        "note": "Optional — Adzuna + JSearch require keys" if not has_source else "Adzuna or JSearch configured",
        "action": "Optional: add ADZUNA_APP_ID/KEY for more jobs",
    })

    # 4. At least one resume saved
    resume_count = db.query(ResumeProfile).count()
    checks.append({
        "step": "4. Resume Saved",
        "done": resume_count > 0,
        "action": "Resumes tab → + Add Resume" if resume_count == 0 else f"{resume_count} resume(s) saved",
    })

    # 5. Initial scrape done
    job_count = db.query(Job).count()
    checks.append({
        "step": "5. First Scrape Run",
        "done": job_count > 0,
        "action": "Dashboard → Scrape button" if job_count == 0 else f"{job_count} jobs in database",
    })

    # 6. First application sent (manual or auto)
    applied = db.query(Application).count()
    checks.append({
        "step": "6. First Application",
        "done": applied > 0,
        "action": "Browse Jobs tab → Apply to a high-score job" if applied == 0 else f"{applied} application(s) sent",
    })

    # 7. LinkedIn (optional)
    li_ok = bool(LINKEDIN_EMAIL)
    checks.append({
        "step": "7. LinkedIn Messaging (Optional)",
        "done": li_ok,
        "action": "Add LINKEDIN_EMAIL + LINKEDIN_PASSWORD to .env" if not li_ok else "Configured",
    })

    # 8. Auto-apply (optional)
    checks.append({
        "step": "8. Auto-Apply (Optional)",
        "done": AUTO_APPLY_ENABLED,
        "action": "Set AUTO_APPLY_ENABLED=true in .env when comfortable" if not AUTO_APPLY_ENABLED else "Enabled",
        "warning": "Only enable after testing — sends real emails to recruiters",
    })

    done_count = sum(1 for c in checks if c["done"])
    total = len(checks)
    pct = round(done_count / total * 100)

    return {
        "completed": done_count,
        "total": total,
        "completion_pct": pct,
        "ready_to_run": done_count >= 5,  # First 5 are required, rest optional
        "checks": checks,
    }
