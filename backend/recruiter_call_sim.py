"""
Mock recruiter screening call simulator.
Different from mock_interview.py (which is deep technical/behavioral).
This simulates the 15-minute initial recruiter call — the first gate.
Gemini plays the recruiter; asks the standard 8 screening questions.
"""
import logging

logger = logging.getLogger(__name__)


# Standard recruiter screening questions
SCREENING_QUESTIONS = [
    "Walk me through your background — give me the 60-second pitch.",
    "Why are you looking to leave your current role?",
    "What's your salary expectation for this role?",
    "When could you start if we moved forward?",
    "Are you currently interviewing elsewhere?",
    "What are 2-3 things that are most important to you in your next role?",
    "Tell me about a recent project you're proud of.",
    "What questions do you have for me about the role or company?",
]


def start_recruiter_call(job_title: str, company: str) -> dict:
    """Returns recruiter greeting + first question."""
    from gemini import _run, PROFILE_SUMMARY
    prompt = f"""You are a friendly recruiter at {company} doing an initial 15-minute screening call
for the {job_title} position.

Candidate background: {PROFILE_SUMMARY}

Greet the candidate briefly (1 sentence), explain you have a few quick questions (1 sentence),
then ask: "{SCREENING_QUESTIONS[0]}"

Keep total response under 80 words. Friendly, professional tone."""
    response = _run(prompt, timeout=30)
    return {
        "recruiter_response": response or f"Hi! Thanks for chatting. Quick 15-min screen for {job_title}. {SCREENING_QUESTIONS[0]}",
        "question_index": 0,
        "questions_remaining": len(SCREENING_QUESTIONS) - 1,
        "history": [{"role": "recruiter", "text": response or SCREENING_QUESTIONS[0]}],
    }


def continue_recruiter_call(job_title: str, company: str, history: list,
                             user_answer: str, question_index: int) -> dict:
    """Continue screening call. Returns next question + brief evaluation."""
    from gemini import _run, PROFILE_SUMMARY

    next_idx = question_index + 1
    if next_idx >= len(SCREENING_QUESTIONS):
        # End the call
        return _end_call(job_title, history, user_answer)

    next_q = SCREENING_QUESTIONS[next_idx]
    convo = "\n".join(
        f"{'Recruiter' if h['role'] == 'recruiter' else 'You'}: {h['text']}"
        for h in history
    )
    prompt = f"""You are a recruiter doing a screening call for {job_title} at {company}.

Candidate: {PROFILE_SUMMARY}

Conversation:
{convo}

Candidate just answered: {user_answer}

Now:
1. Briefly acknowledge their answer (1 sentence, warm but not over-the-top)
2. Ask the next question exactly: "{next_q}"

Keep under 60 words total."""
    response = _run(prompt, timeout=30)
    new_history = history + [
        {"role": "candidate", "text": user_answer},
        {"role": "recruiter", "text": response or f"Got it. {next_q}"},
    ]
    return {
        "recruiter_response": response or f"Got it. {next_q}",
        "question_index": next_idx,
        "questions_remaining": len(SCREENING_QUESTIONS) - 1 - next_idx,
        "history": new_history,
    }


def _end_call(job_title: str, history: list, user_answer: str) -> dict:
    """Wrap up the call with feedback summary."""
    from gemini import _run, PROFILE_SUMMARY

    convo = "\n".join(
        f"{'Recruiter' if h['role'] == 'recruiter' else 'You'}: {h['text']}"
        for h in history
    )
    convo += f"\nYou: {user_answer}"

    prompt = f"""You just finished a mock recruiter screening for {job_title}.

Candidate: {PROFILE_SUMMARY}

Full call:
{convo}

Now provide:
1. Brief friendly close (1 sentence pretending to schedule next steps)
2. Then break character and give the candidate detailed feedback:
   - Overall rating (1-10)
   - Top 2 strong answers (which ones, why)
   - Top 2 answers to improve (which ones, how)
   - Did they ask good questions at the end?
   - Would they pass to next round? (Yes/No/Maybe + reason)

Format clearly. Max 300 words."""
    feedback = _run(prompt, timeout=60)
    new_history = history + [
        {"role": "candidate", "text": user_answer},
        {"role": "recruiter", "text": "Thanks for your time! I'll be in touch within 48 hours."},
    ]
    return {
        "recruiter_response": "Thanks for your time! I'll be in touch within 48 hours.",
        "feedback": feedback or "Good practice session — work on your salary number and questions for the recruiter.",
        "call_ended": True,
        "history": new_history,
        "question_index": len(SCREENING_QUESTIONS),
    }
