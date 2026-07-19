"""Password-reset email delivery (#68, from #39).

Mirrors alert_checker.build_email_notifier's log-before-send pattern (#66): log
a `sending` row, send, resolve to sent/failed. Unlike an alert crossing, a
forgot-password request is never deduplicated (`alert_id=None` skips the
open-delivery check in notifications_service.begin) — each request is its own
user-initiated event, not a sweep that must not double-fire.
"""
import logging

from . import notifications_service, email_sender

logger = logging.getLogger(__name__)


def send_reset_email(user_id: str, to_email: str, reset_link: str) -> bool:
    """Send the password-reset email and log the attempt. Never raises —
    a delivery failure must not surface to a caller that has already committed
    to responding 200 (no account-enumeration via error behavior either).
    """
    subject = "Reset your DSC Quant Analyst password"
    body = (
        "<p>We received a request to reset your password. This link expires "
        "in 30 minutes:</p>"
        f'<p><a href="{reset_link}">{reset_link}</a></p>'
        "<p>If you did not request this, you can ignore this email — your "
        "password will not change.</p>"
    )

    nid = notifications_service.begin(
        user_id=user_id, alert_id=None, channel="email", type_="password_reset",
        subject=subject,
    )
    if nid is None:
        return False

    try:
        ok = email_sender.send_email(to_email, subject, body)
    except Exception as exc:
        logger.exception("Password-reset email to user %s failed to send.", user_id)
        notifications_service.resolve(nid, notifications_service.FAILED, error=str(exc))
        return False

    notifications_service.resolve(
        nid, notifications_service.SENT if ok else notifications_service.FAILED,
    )
    return ok
