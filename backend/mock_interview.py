"""
Mock interview chat with Gemini.
Stateless — pass conversation history with each request.
"""
import json
import logging

logger = logging.getLogger(__name__)


def start_mock_interview(job_title: str, company: str, description: str = "") -> dict:
    """Returns initial Gemini interviewer greeting + first question."""
    from gemini import _run, PROFILE_SUMMARY
    prompt = f"""You are a senior technical interviewer at {company}, conducting an interview for the {job_title} position.

Candidate background: {PROFILE_SUMMARY}
Job context: {description[:600]}

Greet the candidate (1 sentence), then ask your FIRST interview question.
Make it role-appropriate (technical for dev roles, behavioral mix).
Keep your turn under 100 words total.
Begin now."""
    response = _run(prompt, timeout=45)
    return {
        "interviewer_response": response or "Hello! Let's start with: tell me about yourself.",
        "history": [{"role": "interviewer", "text": response or "Tell me about yourself."}],
    }


def continue_mock_interview(job_title: str, company: str, history: list, user_answer: str) -> dict:
    """
    Continue mock interview. Returns interviewer's next question + feedback on previous answer.
    history: list of {role: 'interviewer'|'candidate', text: str}
    """
    from gemini import _run, PROFILE_SUMMARY

    convo = "\n".join(
        f"{'Interviewer' if h['role'] == 'interviewer' else 'Candidate'}: {h['text']}"
        for h in history
    )
    prompt = f"""Continue this mock interview for {job_title} at {company}.

Candidate background: {PROFILE_SUMMARY}

Conversation so far:
{convo}

Candidate's latest answer: {user_answer}

Your response (as interviewer):
1. Briefly evaluate their answer (1 sentence, constructive)
2. Ask the NEXT question — progress difficulty
3. After ~5 questions, give final feedback and end interview

Keep under 120 words. Stay in character as interviewer."""
    response = _run(prompt, timeout=45)
    new_history = history + [
        {"role": "candidate", "text": user_answer},
        {"role": "interviewer", "text": response or "Tell me more about that."},
    ]
    return {
        "interviewer_response": response or "Tell me more about that.",
        "history": new_history,
        "question_count": sum(1 for h in new_history if h["role"] == "interviewer"),
    }


def get_final_feedback(job_title: str, history: list) -> str:
    """Generate detailed feedback after mock interview ends."""
    from gemini import _run, PROFILE_SUMMARY
    convo = "\n".join(
        f"{'Interviewer' if h['role'] == 'interviewer' else 'Candidate'}: {h['text']}"
        for h in history
    )
    prompt = f"""You just finished mock-interviewing this candidate for {job_title}.

Candidate: {PROFILE_SUMMARY}

Full conversation:
{convo}

Provide detailed final feedback:
1. Overall rating (1-10)
2. Top 3 strengths
3. Top 3 areas to improve
4. Specific things to study before the real interview
5. Confidence boost — what they did well

Be honest but encouraging. Max 250 words."""
    return _run(prompt, timeout=60) or "Good practice session! Keep refining your answers."
