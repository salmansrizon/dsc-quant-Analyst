"""Investor profile: the personalization spine's root input (#85, map #84).

One row per user (id = user_id), append-versioned like notification_preferences
— an edit is a new version, the `_current` view resolves the latest, nothing is
ever overwritten (the free tier forbids DML, #52).

`get_profile` is the contract the #88 fit engine and #93 recommendations consume:
it always returns a non-null `InvestorProfile` (an absent profile resolves to the
neutral cold-start object), with `sector_prefs` already parsed from its stored
JSON string to a rank-ordered list. The engine never touches BigQuery or JSON.
"""
import json
from datetime import datetime, timezone

from . import db
from .models import InvestorProfile

# The cold-start object: what a user who never set a profile scores against.
# is_default=True is what the UI's nudge banner keys on, and lets #88 widen its
# reason strings ("based on a balanced default — set your profile to personalize").
NEUTRAL = InvestorProfile(
    goal="growth", risk="med", horizon="medium", sector_prefs=[], is_default=True,
)


def get_profile(user_id: str) -> InvestorProfile:
    """The engine-ready profile for a user — never None (neutral if unset)."""
    row = db.find_current("investor_profiles", id=user_id)
    if not row:
        return NEUTRAL
    return InvestorProfile(
        goal=row["goal"],
        risk=row["risk"],
        horizon=row["horizon"],
        sector_prefs=_parse_sectors(row.get("sector_prefs")),
        is_default=bool(row.get("is_default")),
    )


def save_profile(user_id: str, data: dict) -> InvestorProfile:
    """Append a new profile version (id = user_id is the upsert key).

    A user-set profile is never `is_default` — that flag is reserved for the
    cold-start object `get_profile` synthesizes when no row exists.
    """
    db.append_version("investor_profiles", [{
        "id": user_id,
        "user_id": user_id,
        "goal": data["goal"],
        "risk": data["risk"],
        "horizon": data["horizon"],
        "sector_prefs": json.dumps(data.get("sector_prefs", [])),
        "is_default": False,
        "updated_at": datetime.now(timezone.utc),
        "is_deleted": False,
    }])
    return get_profile(user_id)


def list_sector_names() -> list[str]:
    """The live sector universe — feeds the onboarding multi-select and the
    save-time validation that rejects a sector nobody reports."""
    rows = db.query_rows(f"""
        SELECT DISTINCT Sector
        FROM {db.table_id('lankabd_datamatrix')}
        WHERE Sector IS NOT NULL AND Sector != ''
        ORDER BY Sector
    """)
    return [r["Sector"] for r in rows]


def _parse_sectors(raw) -> list[str]:
    """Stored JSON array string -> rank-ordered list; a bad value degrades to
    empty rather than crashing the whole contract for one corrupt row."""
    if isinstance(raw, list):
        return raw
    if not raw:
        return []
    try:
        val = json.loads(raw)
        return val if isinstance(val, list) else []
    except (ValueError, TypeError):
        return []
