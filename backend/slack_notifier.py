"""
Slack notifications via Incoming Webhook.
Free, no signup beyond Slack workspace.
Setup: Slack → Apps → Incoming Webhooks → Create → copy URL → SLACK_WEBHOOK_URL in .env
"""
import logging
import os

import requests

logger = logging.getLogger(__name__)

_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")


def slack_available() -> bool:
    return bool(_WEBHOOK_URL)


def send_slack(message: str, channel: str = "") -> bool:
    if not slack_available():
        return False
    payload = {"text": message}
    if channel:
        payload["channel"] = channel
    try:
        r = requests.post(_WEBHOOK_URL, json=payload, timeout=8)
        return r.ok
    except Exception as e:
        logger.debug(f"Slack send failed: {e}")
        return False
