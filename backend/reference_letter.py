"""
Reference letter / recommendation request generator.
Helps candidate ask for reference letters from previous managers.
"""
import logging

logger = logging.getLogger(__name__)


def generate_reference_request(reference_name: str, role_at_previous_company: str,
                               company: str, target_role: str = "") -> str:
    """Generate a polite email asking for a reference letter."""
    from gemini import _run
    from config import PROFILE
    prompt = f"""Write a brief, professional email asking for a reference letter.

Sender: {PROFILE.get('name')} ({PROFILE.get('email')})
Recipient: {reference_name} (was their {role_at_previous_company} at {company})
Reason: {PROFILE.get('name')} is applying for {target_role or 'new opportunities'} and needs a reference

Rules:
- Warm but professional
- Acknowledge their busy schedule
- Provide specific context (which roles, deadline)
- Make it easy for them to say yes (offer to draft initial version)
- 3 paragraphs max
- Return ONLY the email body — no subject line"""
    result = _run(prompt, timeout=45)
    if result and len(result) > 100:
        p = PROFILE
        return (
            f"Dear {reference_name},\n\n"
            f"{result}\n\n"
            f"Best regards,\n"
            f"{p.get('name','')}\n"
            f"{p.get('phone','')}\n"
            f"{p.get('email','')}\n"
            f"LinkedIn: {p.get('linkedin','')}"
        )

    # Fallback
    p = PROFILE
    return (
        f"Dear {reference_name},\n\n"
        f"I hope this message finds you well. I'm currently exploring new opportunities for "
        f"{target_role or 'developer roles'} and was wondering if you'd be open to providing "
        f"a reference based on my work during our time at {company}.\n\n"
        f"I understand you're busy, so I'm happy to draft an initial version that you can edit. "
        f"Would the next two weeks work for you?\n\n"
        f"Thank you for considering — your support would mean a lot.\n\n"
        f"Best regards,\n"
        f"{p.get('name','')}\n"
        f"{p.get('phone','')}\n"
        f"{p.get('email','')}"
    )
