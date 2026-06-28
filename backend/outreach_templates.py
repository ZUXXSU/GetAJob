"""
Curated library of proven cold outreach templates.
Gemini personalizes them per target recruiter / company.
Tracks response rate per template variant for A/B testing.
"""
import logging

logger = logging.getLogger(__name__)

# Proven cold outreach templates — short, no questions, easy reply
TEMPLATES = {
    "linkedin_recruiter": {
        "name": "LinkedIn — Recruiter Direct Message",
        "use_when": "Sending to a recruiter you found on LinkedIn",
        "template": (
            "Hi {first_name}, saw you're recruiting for {role} at {company}. "
            "I'm a {experience}yr {tech} dev based in {location}, built {project_example}. "
            "Open to a quick 10-min chat about the role?"
        ),
        "char_limit": 300,
    },
    "linkedin_engineer": {
        "name": "LinkedIn — Engineer at Target Company",
        "use_when": "Sending to an engineer (not recruiter) at company you want to work for",
        "template": (
            "Hi {first_name}, fellow {tech} dev here. I'm looking at {company} for {role} "
            "and noticed your work on {their_focus}. Mind sharing what the team is like? "
            "Happy to send a resume too."
        ),
        "char_limit": 300,
    },
    "email_hr_cold": {
        "name": "Cold Email — HR/Talent",
        "use_when": "Found HR email but role not advertised",
        "template": (
            "Subject: {tech} Developer interested in {company}\n\n"
            "Hi {hr_name},\n\n"
            "I'm {name}, a {experience}yr {tech} developer based in {location}. "
            "I've been following {company}'s work on {company_focus} and would love to "
            "explore openings on your team.\n\n"
            "Recent project: {project_example}. Resume attached.\n\n"
            "Would a 15-min intro call work this week or next?\n\n"
            "Best,\n{name}\n{phone} | {email}"
        ),
        "char_limit": 1000,
    },
    "linkedin_inmail_short": {
        "name": "LinkedIn InMail — Ultra Short",
        "use_when": "First InMail attempt — keep brief for response rate",
        "template": (
            "{first_name} — interested in {role} at {company}. "
            "{experience}yr {tech} dev, {location}-based. "
            "10-min chat?"
        ),
        "char_limit": 200,
    },
    "warm_referral_ask": {
        "name": "Warm Referral Request",
        "use_when": "Asking existing connection for a referral",
        "template": (
            "Hi {first_name}, hope you're well! Saw {company} is hiring for {role} — "
            "would you be open to referring me? I've been building {project_example} and "
            "think I'd be a strong fit. Happy to send my resume so you can decide."
        ),
        "char_limit": 350,
    },
}


def personalize_template(template_key: str, context: dict) -> str:
    """
    Render template with context dict.
    Missing keys substituted with sensible defaults from PROFILE.
    """
    from config import PROFILE
    tpl = TEMPLATES.get(template_key)
    if not tpl:
        return ""

    # Build defaults from PROFILE
    defaults = {
        "name": PROFILE.get("name", "Candidate"),
        "first_name": (PROFILE.get("name", "").split()[0] if PROFILE.get("name") else "Candidate"),
        "email": PROFILE.get("email", ""),
        "phone": PROFILE.get("phone", ""),
        "location": PROFILE.get("location", "").split(",")[0].strip() or "India",
        "experience": int(PROFILE.get("experience_years", 1.5)),
        "tech": "Flutter/iOS",
        "role": "the role",
        "company": "your company",
        "project_example": "cross-platform mobile apps",
        "their_focus": "mobile",
        "company_focus": "mobile development",
        "hr_name": "Hiring Manager",
    }
    defaults.update(context or {})

    try:
        rendered = tpl["template"].format(**defaults)
    except KeyError as e:
        logger.warning(f"Template missing key: {e}")
        rendered = tpl["template"]
    return rendered[:tpl["char_limit"]]


def gemini_personalize(template_key: str, target_company: str, target_role: str,
                      target_person_name: str = "", target_person_role: str = "") -> str:
    """Use Gemini to personalize a template with company research."""
    base = personalize_template(template_key, {
        "company": target_company,
        "role": target_role,
        "first_name": target_person_name or "there",
        "hr_name": target_person_name or "Hiring Manager",
    })
    try:
        from gemini import _run, PROFILE_SUMMARY
        prompt = f"""Personalize this outreach message for higher response rate.
Context: Sending to {target_person_name or 'recruiter'} ({target_person_role or 'recruiter'}) at {target_company} about {target_role}.
Candidate: {PROFILE_SUMMARY}

Base message:
{base}

Make it:
- Reference {target_company} specifically (what they do, recent news, products)
- Sound human, not templated
- Keep under 300 chars for LinkedIn / 1000 for email
- End with low-friction ask
Return ONLY the personalized message."""
        result = _run(prompt, timeout=30)
        return result if result and len(result) > 50 else base
    except Exception:
        return base


def list_templates() -> list:
    return [
        {"key": k, "name": v["name"], "use_when": v["use_when"], "char_limit": v["char_limit"]}
        for k, v in TEMPLATES.items()
    ]
