"""Migrate `price_alerts` rows into the type-discriminated `alerts` table (#66).

    python -m backend.migrations.002_price_alerts_to_alerts     # from repo root
    python migrations/002_price_alerts_to_alerts.py             # from backend/
    ... --dry-run                                               # report only

#66 (from #34) replaced the price-only `price_alerts` schema with a general
`alerts` shape (`type`, `condition_json`, `last_met`, `is_active`). The free
tier forbids DML, so this cannot be an in-place ALTER + UPDATE — instead it
reads `price_alerts_current` and *appends* the transformed rows into `alerts`
(the #51 rebuild pattern). `price_alerts` is left untouched as a record.

Mapping per row:
- type = "price"
- condition_json = {"op": direction, "value": target_price}
- is_active = NOT is_triggered  (a fired one-shot is inactive)
- last_met = the live met-state at migration time, exactly as create_alert
  baselines a new alert. Hardcoding False would fire every already-met alert on
  the first sweep (met=True vs last_met=False is a crossing) — the spurious fire
  #34's "baseline silently, fire nothing" rule exists to prevent.

Idempotent: an id already present in `alerts_current` is skipped, so a re-run
adds nothing.

Run `bootstrap_tables` first so the `alerts` table and view exist.
"""
import argparse
import logging
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend import db  # noqa: E402
from backend import alert_conditions  # noqa: E402
from backend.alerts_service import _current_price  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def _existing_alert_ids() -> set[str]:
    try:
        rows = db.query_rows(f"SELECT id FROM {db.current_view('alerts')}")
    except Exception:
        return set()
    return {r["id"] for r in rows}


def _to_alert_row(pa: dict, now: datetime) -> dict:
    condition_json = alert_conditions.price_condition(
        op=pa.get("direction"), value=pa.get("target_price"),
    )
    # Baseline last_met to the live met-state, exactly as create_alert does, so
    # an already-met migrated alert does not fire spuriously on the first sweep.
    met = alert_conditions.is_met(
        alert_conditions.PRICE, condition_json, _current_price(pa["symbol"]),
    )
    return {
        "id": pa["id"],
        "user_id": pa["user_id"],
        "type": "price",
        "symbol": pa["symbol"],
        "condition_json": condition_json,
        "last_met": met is True,
        "is_active": not bool(pa.get("is_triggered")),
        "created_at": pa.get("created_at") or now,
        "updated_at": now,
        "is_deleted": False,
    }


def migrate(dry_run: bool = False) -> int:
    source = db.query_rows(f"SELECT * FROM {db.current_view('price_alerts')}")
    already = _existing_alert_ids()
    pending = [pa for pa in source if pa["id"] not in already]

    logger.info("price_alerts: %d current, %d already migrated, %d to migrate.",
                len(source), len(source) - len(pending), len(pending))
    if not pending:
        return 0

    now = datetime.now(timezone.utc)
    rows = [_to_alert_row(pa, now) for pa in pending]
    if dry_run:
        for r in rows:
            logger.info("  would migrate %s (%s %s)", r["id"], r["symbol"], r["condition_json"])
        return len(rows)

    db.append_version("alerts", rows)
    logger.info("Migrated %d alert(s) into `alerts`.", len(rows))
    return len(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    migrate(dry_run=args.dry_run)
