"""
Gemini CLI wrapper — all AI features run through the gemini CLI subprocess.
No Claude, no other AI. Just /usr/local/bin/gemini.
"""
import json
import logging
import os
import re
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

logger = logging.getLogger(__name__)

from config import GEMINI_BIN as _GEMINI_BIN, PROFILE
_DEFAULT_TIMEOUT = 90

_NOISE = re.compile(
    r"^\[|^Loaded|^Loading|^Server|^Failed|metric|phase|duration|STARTUP|"
    r"MCP|IDEClient|Stitch|flutter|genkit|dart|osvScanner|securityServer|"
    r"security|compile|schema|extension",
    re.IGNORECASE,
)


def _run(prompt: str, timeout: int = _DEFAULT_TIMEOUT) -> str:
    """Run gemini CLI with prompt, return clean text response."""
    try:
        result = subprocess.run(
            [_GEMINI_BIN, "-o", "text", prompt],
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "NO_COLOR": "1", "TERM": "dumb"},
        )
        lines = result.stdout.splitlines()
        clean = [l for l in lines if not _NOISE.match(l)]
        return "\n".join(clean).strip()
    except subprocess.TimeoutExpired:
        logger.error(f"Gemini timed out after {timeout}s")
        return ""
    except FileNotFoundError:
        logger.error(f"Gemini CLI not found at {_GEMINI_BIN}")
        return ""
    except Exception as e:
        logger.error(f"Gemini error: {e}")
        return ""


def _parse_json(text: str) -> Optional[dict]:
    """Extract JSON from Gemini response (handles markdown code blocks)."""
    text = re.sub(r"```json\n?", "", text)
    text = re.sub(r"```\n?", "", text)
    text = text.strip()
    # Find first { ... } block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        text = match.group(0)
    try:
        return json.loads(text)
    except Exception:
        logger.warning(f"Failed to parse Gemini JSON: {text[:200]}")
        return None


# ── Public API ────────────────────────────────────────────────────────────────

def _build_profile_summary() -> str:
    """Build profile summary string from .env-sourced PROFILE dict."""
    skills = ", ".join(PROFILE.get("skills", [])[:15])
    locs = "/".join(t.title() for t in PROFILE.get("target_locations", []))
    salary = PROFILE.get("min_salary_inr", 500000) // 100_000
    exp = PROFILE.get("experience_years", 1.5)
    remote = "remote OK" if PROFILE.get("accept_remote") else "onsite only"
    return (
        f"{PROFILE.get('name', 'Candidate')} — {exp}yr experience as mobile/fullstack developer. "
        f"Skills: {skills}. "
        f"Location: {locs}, India ({remote}). "
        f"Target: {salary}+ LPA. "
        f"LinkedIn: {PROFILE.get('linkedin', '')}."
    )

PROFILE_SUMMARY = _build_profile_summary()


def _get_resume_content() -> str:
    """Load resume from DB if available, else fall back to PROFILE_SUMMARY."""
    try:
        from database import SessionLocal, ResumeProfile
        db = SessionLocal()
        r = db.query(ResumeProfile).filter_by(name="default").first()
        db.close()
        if r and r.content and len(r.content) > 50:
            return r.content
    except Exception:
        pass
    return PROFILE_SUMMARY


def analyze_job(title: str, company: str, location: str, description: str) -> Optional[dict]:
    """Returns AI analysis of job fit. Uses saved resume if available."""
    desc_snippet = description[:2500] if description else "No description"
    resume_or_profile = _get_resume_content()

    prompt = f"""You are a strict career advisor. Analyze this job for the candidate.

CANDIDATE PROFILE / RESUME:
{resume_or_profile[:1500]}

Job Title: {title}
Company: {company}
Location: {location}
Job Description: {desc_snippet}

CRITICAL RULES:
- If job requires >2 years experience and candidate has ~1.5 years, set apply_recommended=false
- If job requires 5+ years, set ai_score below 40
- Be realistic — don't over-inflate ai_score
- Check if candidate's ACTUAL skills match what's REQUIRED (not just nice-to-have)

Respond ONLY with valid JSON (no markdown, no extra text):
{{
  "ai_score": <integer 0-100, realistic candidate fit score>,
  "required_experience_years": <integer or null, years of exp the job requires>,
  "experience_match": <true if candidate meets experience requirement, else false>,
  "match_reasons": [<3 specific reasons this is a good match, be concrete>],
  "red_flags": [<concrete concerns: overqualification, location, exp gap, etc>],
  "skill_gaps": [<skills explicitly required but candidate lacks>],
  "suggested_salary": "<salary range the candidate should negotiate>",
  "apply_recommended": <true only if ai_score>=65 AND experience_match>,
  "one_line_summary": "<one sentence about this role>"
}}"""
    raw = _run(prompt, timeout=60)
    result = _parse_json(raw)
    if not result:
        return None
    req_exp = result.get("required_experience_years")
    exp_match = bool(result.get("experience_match", True))
    return {
        "ai_score": int(result.get("ai_score", 0)),
        "required_experience_years": int(req_exp) if req_exp is not None else None,
        "experience_match": exp_match,
        "match_reasons": result.get("match_reasons", []),
        "red_flags": result.get("red_flags", []),
        "skill_gaps": result.get("skill_gaps", []),
        "suggested_salary": result.get("suggested_salary", ""),
        "apply_recommended": bool(result.get("apply_recommended", False)),
        "one_line_summary": result.get("one_line_summary", ""),
    }


def generate_cover_letter(title: str, company: str, description: str) -> str:
    """Generate a tailored cover letter for the job."""
    desc_snippet = description[:1500] if description else ""
    prompt = f"""Write a professional, personalized cover letter (3 short paragraphs) for:
Candidate: {PROFILE.get('name', '')}
Phone: {PROFILE.get('phone', '')}
LinkedIn: {PROFILE.get('linkedin', '')}
GitHub: {PROFILE.get('github', '')}

Role: {title} at {company}
Candidate background: {PROFILE_SUMMARY}
Job context: {desc_snippet}

Rules:
- Start with a strong opening (not "I am writing to apply")
- Paragraph 2: 2-3 specific relevant achievements/skills
- Paragraph 3: enthusiasm for this company specifically, call to action
- Professional but not robotic
- Max 250 words
- Return ONLY the cover letter body (no "Subject:", no salutation)"""
    result = _run(prompt, timeout=60)
    return result if result else ""


def tailor_resume(resume_text: str, title: str, company: str, description: str) -> str:
    """Return a tailored version of the resume for this specific job."""
    desc_snippet = description[:1500] if description else ""
    prompt = f"""Tailor this resume for the {title} role at {company}.
Reorder bullet points, emphasize relevant skills, add relevant keywords from the job description.
Keep exact same sections and structure. Don't add fake experience. Don't remove sections.

CURRENT RESUME:
{resume_text[:3000]}

JOB REQUIREMENTS:
{desc_snippet}

Return ONLY the tailored resume text, no commentary."""
    result = _run(prompt, timeout=90)
    return result if result else resume_text


def find_hr_email(company: str, domain: str, description: str) -> str:
    """Try to find or guess the HR email for this company."""
    desc_snippet = description[:800] if description else ""
    prompt = f"""Find the best email to send a job application for {company}.

1. Check this job description for any contact email: {desc_snippet}

2. The company website is: {domain}

Return ONLY a single email address (e.g. hr@company.com).
If you cannot determine the real email, return the most likely format.
No explanation, just the email address."""
    result = _run(prompt, timeout=30)
    # Extract email from response
    emails = re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", result)
    if emails:
        return emails[0]
    # Fallback: guess from domain
    if domain:
        clean = domain.replace("https://", "").replace("http://", "").split("/")[0]
        return f"hr@{clean}"
    return ""


def suggest_resume_improvements(resume_text: str) -> list:
    """Get Gemini's suggestions to improve the resume."""
    prompt = f"""Review this resume and give 5-7 specific, actionable improvements.
Focus on: impact metrics, keyword optimization, clarity, ATS compatibility.

RESUME:
{resume_text[:3000]}

Respond ONLY with a numbered list, one suggestion per line:
1. suggestion one
2. suggestion two
3. suggestion three"""
    raw = _run(prompt, timeout=60)
    if not raw:
        return []
    lines = raw.splitlines()
    suggestions = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Strip leading number/bullet
        cleaned = re.sub(r"^[\d]+[.)]\s*|^[-*•]\s*", "", line).strip()
        if len(cleaned) > 10:
            suggestions.append(cleaned)
    return suggestions if suggestions else [raw]


def select_best_resume(job_title: str, job_description: str, resumes: list) -> Optional[dict]:
    """
    Pick the best resume for this job from a list of resume dicts.
    Each resume: {id, name, content, target_roles, description}
    Returns the chosen resume dict, or None if list is empty.
    """
    if not resumes:
        return None
    if len(resumes) == 1:
        return resumes[0]

    resume_list = "\n".join(
        f"{i+1}. \"{r['name']}\" — targets: {r.get('target_roles', [])} — {r.get('description', '')}"
        for i, r in enumerate(resumes)
    )
    prompt = f"""Pick the BEST resume for this job.

Job: {job_title}
Description snippet: {job_description[:400]}

Resumes available:
{resume_list}

Reply with ONLY the number (1, 2, 3...) of the best resume. No explanation."""
    raw = _run(prompt, timeout=45)
    m = re.search(r'\d+', raw)
    if m:
        idx = int(m.group(0)) - 1
        if 0 <= idx < len(resumes):
            return resumes[idx]
    return resumes[0]


# ── Batch Analysis ─────────────────────────────────────────────────────────────

_batch_progress: dict = {"total": 0, "done": 0, "failed": 0, "running": False}


def get_batch_progress() -> dict:
    return dict(_batch_progress)


def analyze_all_jobs_batch(max_workers: int = 4) -> dict:
    """
    Analyze ALL unanalyzed jobs in parallel using Gemini CLI.
    Uses ThreadPoolExecutor — Gemini CLI runs as subprocess so GIL doesn't block.
    """
    global _batch_progress
    from database import SessionLocal, Job, AIAnalysis

    db = SessionLocal()
    analyzed_ids = {row.job_id for row in db.query(AIAnalysis.job_id).all()}
    pending = [
        (j.id, j.title or "", j.company or "", j.location or "", j.description or "")
        for j in db.query(Job).all()
        if j.id not in analyzed_ids
    ]
    db.close()

    _batch_progress = {"total": len(pending), "done": 0, "failed": 0, "running": True}
    logger.info(f"Batch analysis: {len(pending)} jobs to analyze with {max_workers} workers")

    def _analyze_one(job_tuple):
        job_id, title, company, location, description = job_tuple
        try:
            result = analyze_job(title, company, location, description)
            if result:
                _save_analysis(job_id, result)
                return True
        except Exception as e:
            logger.error(f"Batch analysis error job {job_id}: {e}")
        return False

    done = 0
    failed = 0
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_analyze_one, jd): jd for jd in pending}
        for future in as_completed(futures):
            if future.result():
                done += 1
                _batch_progress["done"] = done
            else:
                failed += 1
                _batch_progress["failed"] = failed

    _batch_progress["running"] = False
    logger.info(f"Batch analysis complete: {done} done, {failed} failed")
    return {"total": len(pending), "done": done, "failed": failed}


def _save_analysis(job_id: int, result: dict):
    """Save analysis result to DB."""
    from database import SessionLocal, AIAnalysis
    import json as _json
    db = SessionLocal()
    try:
        existing = db.query(AIAnalysis).filter_by(job_id=job_id).first()
        if existing:
            existing.ai_score = result["ai_score"]
            existing.match_reasons = _json.dumps(result["match_reasons"])
            existing.red_flags = _json.dumps(result["red_flags"])
            existing.skill_gaps = _json.dumps(result["skill_gaps"])
            existing.suggested_salary = result["suggested_salary"]
            existing.apply_recommended = result["apply_recommended"]
            existing.one_line_summary = result["one_line_summary"]
        else:
            db.add(AIAnalysis(
                job_id=job_id,
                ai_score=result["ai_score"],
                match_reasons=_json.dumps(result["match_reasons"]),
                red_flags=_json.dumps(result["red_flags"]),
                skill_gaps=_json.dumps(result["skill_gaps"]),
                suggested_salary=result["suggested_salary"],
                apply_recommended=result["apply_recommended"],
                one_line_summary=result["one_line_summary"],
            ))
        db.commit()
    finally:
        db.close()


def score_jobs_batch(jobs: list) -> list:
    """
    Quick AI re-ranking of a batch of jobs. Returns list of (job_id, ai_score).
    Used after scraping to prioritize which jobs to show first.
    """
    if not jobs:
        return []
    job_list = "\n".join(
        f"{i+1}. [{j.get('id', i)}] {j.get('title','')} at {j.get('company','')} — {j.get('location','')} (rule score: {j.get('match_score',0)})"
        for i, j in enumerate(jobs[:20])
    )
    prompt = f"""Re-rank these jobs for: {PROFILE_SUMMARY}

Jobs:
{job_list}

Respond ONLY with valid JSON array ordered best-first:
[{{"id": <job_id>, "ai_score": <0-100>, "reason": "<5 words>"}}, ...]
Include ALL {min(len(jobs), 20)} jobs."""
    raw = _run(prompt, timeout=45)
    raw = re.sub(r"```json\n?|```\n?", "", raw).strip()
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass
    return []
