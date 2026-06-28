"""
AI Job Search Consultant — open-ended chat with Gemini.
Has full context of candidate profile + current state of applications.
For any question: "should I take this offer?", "is X company good?",
"how to negotiate?", "is this resume bullet good?"
"""
import logging

logger = logging.getLogger(__name__)


def chat(history: list, user_message: str) -> dict:
    """
    Multi-turn chat with Gemini consultant.
    history: list of {role: 'user'|'assistant', text: str}
    """
    from gemini import _run, PROFILE_SUMMARY
    from database import SessionLocal, Job, Application

    # Get current state for context
    db = SessionLocal()
    try:
        total_jobs = db.query(Job).count()
        applied = db.query(Job).filter(Job.status == "applied").count()
        interviews = db.query(Application).filter(Application.stage == "interview").count()
        offers = db.query(Application).filter(Application.stage == "offer").count()
        high_match = db.query(Job).filter(Job.match_score >= 80, Job.status == "new").count()
    finally:
        db.close()

    context = f"""You are an experienced career coach helping {PROFILE_SUMMARY.split('—')[0].strip()} find their next role.

CANDIDATE PROFILE:
{PROFILE_SUMMARY}

CURRENT STATE (live):
- {total_jobs} jobs discovered in system
- {high_match} high-match (80+) jobs ready to apply
- {applied} applications sent
- {interviews} interviews in pipeline
- {offers} offers received

You give direct, specific, honest advice. No corporate fluff. Use Indian market context.
You can ask clarifying questions if needed.
Keep responses under 200 words unless explicitly asked for detail."""

    convo_str = "\n".join(
        f"{'User' if h['role'] == 'user' else 'Coach'}: {h['text']}"
        for h in history[-10:]  # Last 10 turns only for context window
    )

    prompt = f"""{context}

Conversation so far:
{convo_str}

User: {user_message}

Coach:"""

    response = _run(prompt, timeout=60)
    new_history = history + [
        {"role": "user", "text": user_message},
        {"role": "assistant", "text": response or "Could you rephrase that?"},
    ]
    return {
        "response": response or "Could you rephrase that?",
        "history": new_history,
    }
