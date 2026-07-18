"""Alert queries + mutations over the type-discriminated `alerts` table (#66).

Append-only: mutations record a new version and reads go through
`alerts_current`. See db.append_version (#52) — BigQuery's free tier forbids DML.

The public API is still price-only (symbol / target_price / direction) so the
frontend is untouched; internally each alert is stored in the general
type-discriminated shape (`type`, `condition_json`) that Phase 2's other alert
types will share. See alert_conditions for the pure logic and alert_checker for
the edge-trigger sweep.
"""
import uuid
from datetime import datetime, timezone

from google.cloud import bigquery

from . import db
from . import alert_conditions


def _current_price(symbol: str) -> float | None:
    """The symbol's latest price from the datamatrix, or None if unknown.

    Used to baseline `last_met` at creation: an alert created while its
    condition is *already* met must not fire on the next sweep (there was no
    crossing). Baselining here, at creation, is what makes that true — #34's
    "an alert created while already-met never fires".
    """
    rows = db.query_rows(
        f"SELECT d.LTP AS price FROM {db.table_id('lankabd_datamatrix')} d "
        f"WHERE d.Symbol = @sym LIMIT 1",
        [bigquery.ScalarQueryParameter("sym", "STRING", symbol)],
    )
    if not rows:
        return None
    return rows[0].get("price")


def _to_item(row: dict) -> dict:
    """A stored alert row rendered back into the price-alert API shape.

    Reconstructs target_price/direction from condition_json and reports
    is_triggered as the inverse of is_active — a one-shot alert that has fired
    is inactive, which is exactly what "triggered" meant in the old API.
    """
    cond = alert_conditions.parse_condition(row.get("condition_json"))
    return {
        "id": row["id"],
        "symbol": row["symbol"],
        "target_price": cond.get("value"),
        "direction": cond.get("op"),
        "is_triggered": not row.get("is_active", True),
        "created_at": row.get("created_at"),
        "current_price": row.get("current_price"),
    }


def get_alerts(user_id: str):
    sql = f"""
        SELECT a.id, a.symbol, a.condition_json, a.is_active, a.created_at,
               d.LTP AS current_price
        FROM {db.current_view('alerts')} a
        {db.price_join('a')}
        WHERE a.user_id = @uid
        ORDER BY a.created_at DESC
    """
    params = [bigquery.ScalarQueryParameter("uid", "STRING", user_id)]
    return [_to_item(r) for r in db.query_rows(sql, params)]


def active_alerts() -> list[dict]:
    """Every active alert, across all users, with its symbol's current price.

    The edge-trigger sweep needs *all* active alerts, not just unmet ones — it
    compares each alert's current is_met against its stored `last_met` to find
    crossings, so an already-met alert must still be looked at (it may cross
    back down). The join is done in SQL because the case differs — alerts store
    `symbol`, the datamatrix stores `Symbol` (the bug that made #48 never fire).
    """
    return db.query_rows(f"""
        SELECT a.id, a.user_id, a.type, a.symbol, a.condition_json, a.last_met,
               d.LTP AS current_price
        FROM {db.current_view('alerts')} a
        {db.price_join('a')}
        WHERE COALESCE(a.is_active, TRUE)
    """)


def _find_alert(alert_id: str, user_id: str) -> dict | None:
    """One of the user's current alerts, or None. Scoped by owner."""
    return db.find_current("alerts", id=alert_id, user_id=user_id)


def create_alert(user_id: str, data: dict):
    """Create a price alert, baselining its edge state against the live price."""
    aid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    symbol = data["symbol"].upper()
    condition_json = alert_conditions.price_condition(
        op=data["direction"], value=data["target_price"],
    )

    # Baseline last_met at creation so an already-met alert does not fire on the
    # first sweep. is_met is tri-state; an unknown price (None) baselines to
    # False — we have never observed it met, so the first met reading is a real
    # first crossing.
    met = alert_conditions.is_met(
        alert_conditions.PRICE, condition_json, _current_price(symbol),
    )

    db.append_version("alerts", [{
        "id": aid,
        "user_id": user_id,
        "type": alert_conditions.PRICE,
        "symbol": symbol,
        "condition_json": condition_json,
        "last_met": met is True,
        "is_active": True,
        "created_at": now,
        "is_deleted": False,
        "updated_at": now,
    }])
    return {"id": aid, "symbol": symbol}


def delete_alert(alert_id: str, user_id: str) -> bool:
    """Tombstone one of the user's alerts. Returns whether it existed."""
    alert = _find_alert(alert_id, user_id)
    if not alert:
        return False
    db.tombstone("alerts", alert)
    return True


def record_state(alert: dict, met: bool, fired: bool) -> None:
    """Persist an alert's new edge state after a sweep.

    Called only when `last_met` actually flips (an append is a transition, so
    append volume tracks real crossings, not checks — #34). `fired` sets
    is_active=False, the one-shot: a fired alert does not re-arm in Phase 1.

    Reads the full current row first so the version carries every column (a
    partial append would blank the rest under the latest-version view).
    """
    current = db.find_current("alerts", id=alert["id"])
    if not current:
        return
    now = datetime.now(timezone.utc)
    db.append_version("alerts", [{
        **current,
        "last_met": met,
        "is_active": not fired and current.get("is_active", True),
        "updated_at": now,
    }])
