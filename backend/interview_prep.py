"""
Interview preparation assistant.
When an application reaches 'interview' stage, Gemini generates:
- Top 10 likely interview questions
- Suggested answers based on resume
- Company research summary
- Salary negotiation talking points
"""
import logging

logger = logging.getLogger(__name__)


def generate_interview_prep(job_title: str, company: str, description: str, resume_content: str = "") -> dict:
    """Generate full interview prep pack for a job. Cached in DB by caller."""
    from gemini import _run, PROFILE_SUMMARY

    resume_ctx = resume_content[:1500] if resume_content else PROFILE_SUMMARY

    questions_prompt = f"""Generate the top 10 interview questions for this role and ideal answers based on the candidate.

Role: {job_title} at {company}
Job Description: {description[:1200]}
Candidate: {resume_ctx}

Format as numbered list:
Q1: [question]
A1: [3-4 sentence ideal answer using candidate's actual experience]

Q2: ...

Cover: technical skills, behavioral (STAR), culture fit, salary expectations."""

    company_prompt = f"""Research summary for interview at {company}.
Include: company overview, tech stack if known, culture signals, what to research before interview.
Max 200 words. Practical and actionable."""

    salary_prompt = f"""Salary negotiation talking points for {job_title} at {company} in Mumbai/India.
Candidate has {PROFILE_SUMMARY.split('experience')[0].strip().split('—')[-1].strip()} experience.
Give: opening ask, walk-away number, counter-offer strategy, non-salary benefits to negotiate.
Max 150 words."""

    questions = _run(questions_prompt, timeout=90)
    company_research = _run(company_prompt, timeout=45)
    salary_tips = _run(salary_prompt, timeout=45)

    return {
        "questions_and_answers": questions or "",
        "company_research": company_research or "",
        "salary_negotiation": salary_tips or "",
        "generated_at": None,
    }


def get_or_generate_prep(job_id: int) -> dict:
    """Get cached prep or generate fresh. Saves to DB."""
    from database import SessionLocal, Job, AIAnalysis, ResumeProfile
    db = SessionLocal()
    try:
        j = db.query(Job).filter(Job.id == job_id).first()
        if not j:
            return {}
        analysis = db.query(AIAnalysis).filter_by(job_id=job_id).first()
        # Check if already have interview prep cached in analysis notes
        if analysis and getattr(analysis, 'interview_prep', None):
            import json
            try:
                return json.loads(analysis.interview_prep)
            except Exception:
                pass
        resume = db.query(ResumeProfile).filter_by(is_default=True).first()
        resume_content = resume.content if resume else ""
        prep = generate_interview_prep(j.title, j.company, j.description or "", resume_content)
        # Cache in analysis
        import json
        if not analysis:
            analysis = AIAnalysis(job_id=job_id)
            db.add(analysis)
        analysis.interview_prep = json.dumps(prep)
        db.commit()
        return prep
    finally:
        db.close()
