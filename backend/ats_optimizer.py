"""
ATS (Applicant Tracking System) keyword optimizer.
Compares job description keywords against resume content.
Finds missing keywords that would get the resume filtered out by ATS.
"""
import re
import logging

logger = logging.getLogger(__name__)

# Common ATS-relevant skill keywords
_TECH_PATTERNS = re.compile(
    r'\b(swift|kotlin|dart|flutter|react|node\.?js|angular|python|java|javascript|'
    r'typescript|sql|mysql|mongodb|postgresql|firebase|aws|docker|git|xcode|'
    r'android\s*studio|rest\s*api|graphql|redux|redux|bloc|mvvm|mvc|'
    r'agile|scrum|ci/?cd|unit\s*test|widget\s*test|swiftui|uikit|jetpack|'
    r'compose|fastlane|testflight|google\s*play|app\s*store|cross.platform|'
    r'native|hybrid|saas|b2b|b2c|microservices|kafka|redis|elasticsearch)\b',
    re.IGNORECASE,
)


def extract_keywords(text: str) -> set:
    """Extract ATS-relevant keywords from text."""
    return {m.group(0).lower() for m in _TECH_PATTERNS.finditer(text or "")}


def analyze_ats_match(job_description: str, resume_content: str) -> dict:
    """
    Compare job description keywords vs resume.
    Returns missing keywords, present keywords, and ATS score estimate.
    """
    job_keywords = extract_keywords(job_description)
    resume_keywords = extract_keywords(resume_content)

    present = job_keywords & resume_keywords
    missing = job_keywords - resume_keywords
    extra = resume_keywords - job_keywords

    ats_score = round(len(present) / max(len(job_keywords), 1) * 100)

    return {
        "ats_score": ats_score,
        "job_keywords_total": len(job_keywords),
        "present_keywords": sorted(present),
        "missing_keywords": sorted(missing),
        "extra_in_resume": sorted(extra),
        "recommendation": _recommend(missing, ats_score),
    }


def _recommend(missing: set, ats_score: int) -> str:
    if ats_score >= 80:
        return "Strong ATS match. Resume should pass most automated filters."
    elif ats_score >= 60:
        return f"Decent match. Consider adding: {', '.join(list(missing)[:5])}"
    elif missing:
        return f"Low ATS score. Add these keywords to resume: {', '.join(list(missing)[:8])}"
    return "No specific keywords detected in job description."


def gemini_ats_analysis(job_title: str, job_description: str, resume_content: str) -> dict:
    """Full Gemini-powered ATS analysis with tailored advice."""
    basic = analyze_ats_match(job_description, resume_content)

    try:
        from gemini import _run
        prompt = f"""Analyze ATS compatibility for this application:

Job: {job_title}
Job Requirements (first 800 chars): {job_description[:800]}
Resume (first 800 chars): {resume_content[:800]}

Rule-based ATS score: {basic['ats_score']}%
Missing keywords detected: {', '.join(basic['missing_keywords'][:10])}

Provide:
1. Which missing keywords are most critical to add
2. Exact sentences to add/modify in the resume to include them naturally
3. Overall ATS optimization priority (High/Medium/Low)

Keep response under 200 words. Be specific and actionable."""
        advice = _run(prompt, timeout=45)
        basic["gemini_advice"] = advice
    except Exception as e:
        logger.warning(f"Gemini ATS analysis failed: {e}")
        basic["gemini_advice"] = basic["recommendation"]

    return basic
