"""Resend email adapter (#66, from #34).

The one place that talks to the email provider. #34 chose Resend (HTTP API, not
SMTP): one `RESEND_API_KEY`, a verified sender domain (a launch task — the
onboarding domain lands in spam). Shared with #39's password-reset email.

Kept behind a plain function so the notifier seam alert_checker already expects
stays a simple boolean, and tests fake the send without touching the network.
"""
import logging
import os

import requests

logger = logging.getLogger(__name__)

RESEND_ENDPOINT = "https://api.resend.com/emails"
# Until the verified sender domain lands, override via env. Resend rejects an
# unverified `from`, so a real send needs RESEND_FROM set to the verified domain.
DEFAULT_FROM = os.environ.get("RESEND_FROM", "alerts@dsc-quant.example")


def send_email(to: str, subject: str, html: str) -> bool:
    """Send one email via Resend. Returns whether the provider accepted it.

    Raises RuntimeError if RESEND_API_KEY is unset — a misconfigured deploy
    should fail loudly, not silently drop every alert.
    """
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        raise RuntimeError("RESEND_API_KEY is not set — cannot send email")

    resp = requests.post(
        RESEND_ENDPOINT,
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json"},
        json={"from": DEFAULT_FROM, "to": [to], "subject": subject, "html": html},
        timeout=10,
    )
    if resp.status_code >= 400:
        logger.error("Resend rejected email to %s: %s %s",
                     to, resp.status_code, resp.text[:200])
        return False
    return True
