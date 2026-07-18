"""Delivery log + the log-before-send lock (#66, from #34).

Every send is logged *before* it goes out: append a `sending` row, send, then
append the row again resolved to `sent` or `failed`. A mid-sweep timeout can
then never cause a silent re-send — the `sending`/`sent` row is the lock, and
`begin` refuses to start a second delivery for a crossing that already has one.

Append-only (#52): a status change is a new version; `notifications_current`
resolves the latest per id. Transactional email (#39 password reset) logs here
too, with alert_id NULL.
"""
import uuid
from datetime import datetime, timezone

from google.cloud import bigquery

from . import db

SENDING = "sending"
SENT = "sent"
FAILED = "failed"
BOUNCED = "bounced"


def _has_open_delivery(alert_id: str, type_: str) -> bool:
    """Whether a sending/sent notification already exists for this crossing.

    The lock: a fired alert produces one delivery (one-shot). If a `sending` or
    `sent` row is already current for it, a re-run must not send again. Keyed on
    alert_id + type so a password_reset (alert_id NULL) never collides with an
    alert's delivery.
    """
    rows = db.query_rows(
        f"""
        SELECT id FROM {db.current_view('notifications')}
        WHERE alert_id = @aid AND type = @type
          AND status IN ('{SENDING}', '{SENT}')
        LIMIT 1
        """,
        [
            bigquery.ScalarQueryParameter("aid", "STRING", alert_id),
            bigquery.ScalarQueryParameter("type", "STRING", type_),
        ],
    )
    return bool(rows)


def begin(user_id: str, alert_id: str | None, channel: str, type_: str,
          subject: str) -> str | None:
    """Claim a delivery: append a `sending` row and return its id.

    Returns None if a delivery for this crossing is already open/done — the
    caller must then skip the send. `alert_id` is None for transactional email,
    which is never deduplicated this way (each reset is its own event).
    """
    if alert_id is not None and _has_open_delivery(alert_id, type_):
        return None

    nid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    db.append_version("notifications", [{
        "id": nid,
        "user_id": user_id,
        "alert_id": alert_id,
        "channel": channel,
        "type": type_,
        "subject": subject,
        "status": SENDING,
        "attempts": 1,
        "error": None,
        "created_at": now,
        "is_deleted": False,
        "updated_at": now,
    }])
    return nid


def resolve(notification_id: str, status: str, error: str | None = None) -> None:
    """Resolve a claimed delivery to sent/failed/bounced.

    Carries the full current row forward so the version keeps every column under
    the latest-version view.
    """
    current = db.find_current("notifications", id=notification_id)
    if not current:
        return
    db.append_version("notifications", [{
        **current,
        "status": status,
        "error": error,
        "updated_at": datetime.now(timezone.utc),
    }])
