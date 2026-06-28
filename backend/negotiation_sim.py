"""
Salary negotiation simulator.
Gemini plays the hiring manager. You practice the negotiation conversation.
Tracks counter-offer techniques used. Gives feedback on confidence + tactics.
"""
import logging

logger = logging.getLogger(__name__)


def start_negotiation(job_title: str, company: str, initial_offer_inr: int,
                     target_inr: int) -> dict:
    """Start negotiation simulation. Hiring manager opens with the initial offer."""
    from gemini import _run, PROFILE_SUMMARY

    prompt = f"""You are the hiring manager at {company} extending a job offer for {job_title}.

Candidate: {PROFILE_SUMMARY}

You're presenting an initial offer of ₹{initial_offer_inr:,} INR/year (base).
Open the conversation:
1. Congratulate them briefly (1 sentence)
2. State the offer clearly with: base salary, equity (if any), bonus structure, benefits
3. Express enthusiasm but mention there's some flexibility
4. Ask them how they're feeling about it

Stay in character. Be friendly but firm — you have budget but not unlimited.
Max 100 words."""

    response = _run(prompt, timeout=30)
    return {
        "manager_response": response or f"Glad to extend an offer of ₹{initial_offer_inr:,}. What are your thoughts?",
        "initial_offer": initial_offer_inr,
        "candidate_target": target_inr,
        "current_offer": initial_offer_inr,
        "round": 1,
        "history": [{"role": "manager", "text": response or ""}],
    }


def continue_negotiation(job_title: str, company: str, history: list,
                         user_response: str, current_offer: int, target: int,
                         round_num: int) -> dict:
    """Continue negotiation. Manager may concede, hold, or counter."""
    from gemini import _run

    convo = "\n".join(
        f"{'Manager' if h['role'] == 'manager' else 'You'}: {h['text']}"
        for h in history
    )

    prompt = f"""You are the hiring manager at {company} for {job_title} negotiating with the candidate.

Current offer on the table: ₹{current_offer:,} INR
Round: {round_num} of negotiation

Conversation so far:
{convo}

Candidate just said: {user_response}

Respond as the hiring manager:
1. Evaluate their counter-argument (was it strong? data-backed? polite?)
2. Decide your move: concede 5-15%, hold firm with explanation, OR add non-salary perks
3. Stay realistic — by round 3+ you should reach final position
4. Stay in character. Max 100 words.

After 4 rounds, the negotiation is over — wrap up with final offer (yes or no)."""

    response = _run(prompt, timeout=30)

    # Parse if manager conceded (look for numbers in response)
    import re
    new_offer = current_offer
    nums = re.findall(r'₹?\s*([\d,]+(?:\.\d+)?)\s*(?:LPA|L|INR|/yr|/year)?', response or "")
    for n in nums:
        try:
            val = float(n.replace(",", ""))
            if val < 200:
                val *= 100_000
            if current_offer < val < target * 1.1:
                new_offer = int(val)
                break
        except Exception:
            continue

    new_history = history + [
        {"role": "candidate", "text": user_response},
        {"role": "manager", "text": response or ""},
    ]

    ended = round_num >= 4 or "final offer" in (response or "").lower() or "accept" in (response or "").lower()
    feedback = ""
    if ended:
        feedback = _generate_feedback(job_title, new_history, current_offer, new_offer, target)

    return {
        "manager_response": response,
        "current_offer": new_offer,
        "round": round_num + 1,
        "history": new_history,
        "ended": ended,
        "feedback": feedback,
        "gain": new_offer - current_offer,
    }


def _generate_feedback(job_title: str, history: list, original: int,
                       final: int, target: int) -> str:
    from gemini import _run, PROFILE_SUMMARY

    convo = "\n".join(
        f"{'Manager' if h['role'] == 'manager' else 'You'}: {h['text']}"
        for h in history
    )
    gain = final - original
    hit_target = final >= target

    prompt = f"""Break character. Give the candidate feedback on their negotiation.

Candidate: {PROFILE_SUMMARY}
Job: {job_title}

Full negotiation:
{convo}

Outcome:
- Started at ₹{original:,}
- Ended at ₹{final:,}
- Their target was ₹{target:,}
- Gain: ₹{gain:,} ({"hit target" if hit_target else "below target"})

Provide:
1. Overall rating (1-10)
2. Top 2 things they did well (specific quotes if possible)
3. Top 2 things to improve next time
4. The "winning phrase" they could have used (specific line)
5. Final tip for the real negotiation

Be direct. Max 250 words."""

    return _run(prompt, timeout=60) or "Good practice — practice more for real confidence."
