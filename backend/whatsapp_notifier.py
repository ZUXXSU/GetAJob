"""
WhatsApp notifications via Twilio.
Alternative/addition to Telegram. Most Indians prefer WhatsApp.
Free Twilio sandbox: send up to 1000 msg/month.
Setup: https://www.twilio.com/console/sms/whatsapp/sandbox
"""
import logging
import os

import requests

logger = logging.getLogger(__name__)

_TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
_TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
_TWILIO_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")  # Twilio sandbox default
_TWILIO_TO = os.getenv("TWILIO_WHATSAPP_TO", "")  # e.g. whatsapp:+919372923253


def whatsapp_available() -> bool:
    return bool(_TWILIO_SID and _TWILIO_TOKEN and _TWILIO_TO)


def send_whatsapp(message: str) -> bool:
    if not whatsapp_available():
        return False
    try:
        r = requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{_TWILIO_SID}/Messages.json",
            data={"From": _TWILIO_FROM, "To": _TWILIO_TO, "Body": message[:1600]},
            auth=(_TWILIO_SID, _TWILIO_TOKEN),
            timeout=10,
        )
        return r.status_code in (200, 201)
    except Exception as e:
        logger.debug(f"WhatsApp send failed: {e}")
        return False
