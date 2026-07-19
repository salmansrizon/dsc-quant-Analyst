"""Per-user notification channel preferences (#78, ported from main).

main used UPDATE DML with an exists-check; here it is an append-only upsert —
one version per change, keyed by user_id, resolved through the `_current` view.
`channels_enabled` is stored as a JSON array string and returned as a list.
"""
import json
from datetime import datetime, timezone

from . import db


def get_prefs(user_id: str) -> dict | None:
    row = db.find_current("notification_preferences", id=user_id)
    if not row:
        return None
    ce = row.get("channels_enabled")
    if isinstance(ce, str):
        try:
            row["channels_enabled"] = json.loads(ce)
        except (ValueError, TypeError):
            row["channels_enabled"] = []
    return row


def update_prefs(user_id: str, data: dict) -> dict:
    """Append a new version of the user's prefs (id = user_id is the upsert key)."""
    db.append_version("notification_preferences", [{
        "id": user_id,
        "user_id": user_id,
        "telegram_chat_id": data.get("telegram_chat_id"),
        "whatsapp_number": data.get("whatsapp_number"),
        "email": data.get("email"),
        "web_push_subscription": data.get("web_push_subscription"),
        "channels_enabled": json.dumps(data.get("channels_enabled", [])),
        "updated_at": datetime.now(timezone.utc),
        "is_deleted": False,
    }])
    return get_prefs(user_id)
