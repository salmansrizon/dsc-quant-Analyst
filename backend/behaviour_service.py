"""Behaviour capture (#86, spine #84): append raw implicit-signal events.

The server stamps id / user_id / event_date / created_at so the client cannot
spoof identity or timing. Raw events are immutable and age out via the table's
8-day partition expiry (no DELETE) — so this only ever appends (insert_rows,
never append_version: the raw log has no version columns).
"""
import json
import uuid
from datetime import datetime, timezone

from . import db

_TABLE = "behaviour_events"


def _row(user_id: str, ev: dict, now: datetime) -> dict:
    payload = ev.get("payload")
    return {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "event_type": ev["event_type"],
        "symbol": (ev.get("symbol") or None) and ev["symbol"].upper(),
        "sector": ev.get("sector") or None,
        "payload": json.dumps(payload) if payload else None,
        "event_date": now.date().isoformat(),
        "created_at": now,
    }


def record_events(user_id: str, events: list[dict]) -> int:
    """Append a batch of raw events. Returns how many landed."""
    if not events:
        return 0
    now = datetime.now(timezone.utc)
    db.insert_rows(_TABLE, [_row(user_id, e, now) for e in events])
    return len(events)


def emit(user_id: str, event_type: str, symbol: str | None = None,
         sector: str | None = None) -> None:
    """Record one event server-side — the path watchlist/portfolio handlers use,
    so an explicit action is captured without a frontend round-trip."""
    record_events(user_id, [{"event_type": event_type, "symbol": symbol, "sector": sector}])
