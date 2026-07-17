"""Create the append-only tables and their `_current` views (ticket #52).

Run once per environment, and again after changing a schema below:

    python -m backend.bootstrap_tables          # from the repo root
    python bootstrap_tables.py                  # from backend/

Idempotent: tables are created if absent (never replaced — that would drop
data), and views are CREATE OR REPLACE.

Only DDL and load jobs are used, because BigQuery's free tier forbids DML.
"""
import logging

from google.cloud import bigquery

try:
    from backend import db
except ImportError:  # standalone: cwd=backend
    import db

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

_TS = "TIMESTAMP"
_STR = "STRING"

# Explicit schemas: these tables were previously created by load-job autodetect,
# which is how `users.phone` ended up INTEGER and broke signup (#51).
SCHEMAS = {
    "users": [
        ("id", _STR), ("email", _STR), ("phone", _STR), ("password_hash", _STR),
        ("full_name", _STR), ("role", _STR),
        ("created_at", _TS), ("updated_at", _TS), ("is_deleted", "BOOL"),
    ],
    "watchlists": [
        ("id", _STR), ("user_id", _STR), ("symbol", _STR),
        ("added_at", _TS), ("updated_at", _TS), ("is_deleted", "BOOL"),
    ],
    "portfolios": [
        ("id", _STR), ("user_id", _STR), ("symbol", _STR),
        ("buy_price", "FLOAT64"), ("quantity", "INT64"), ("buy_date", _STR),
        ("price_target", "FLOAT64"), ("stop_loss", "FLOAT64"), ("notes", _STR),
        ("created_at", _TS), ("updated_at", _TS), ("is_deleted", "BOOL"),
    ],
    "price_alerts": [
        ("id", _STR), ("user_id", _STR), ("symbol", _STR),
        ("target_price", "FLOAT64"), ("direction", _STR),
        ("is_triggered", "BOOL"), ("triggered_at", _TS),
        ("created_at", _TS), ("updated_at", _TS), ("is_deleted", "BOOL"),
    ],
}


def _table_exists(name: str) -> bool:
    try:
        db.client().get_table(db.qualified_name(name))
        return True
    except Exception:
        return False


def _create_table(name: str, columns) -> None:
    cols = ", ".join(f"{c} {t}" for c, t in columns)
    db.client().query(f"CREATE TABLE {db.table_id(name)} ({cols})").result()


def _add_missing_columns(name: str, columns) -> list[str]:
    """Add columns an existing table lacks. ADD COLUMN is DDL, so it is free."""
    existing = {f.name for f in db.client().get_table(db.qualified_name(name)).schema}
    added = []
    for col, col_type in columns:
        if col not in existing:
            db.client().query(
                f"ALTER TABLE {db.table_id(name)} ADD COLUMN {col} {col_type}"
            ).result()
            added.append(col)
    return added


def bootstrap() -> None:
    for table, key in db.VERSIONED_TABLES.items():
        columns = SCHEMAS[table]  # KeyError here means the two lists drifted
        if not _table_exists(table):
            _create_table(table, columns)
            logger.info("created table %s", table)
        else:
            added = _add_missing_columns(table, columns)
            if added:
                logger.info("added columns to %s: %s", table, ", ".join(added))
            else:
                logger.info("table %s already current", table)

        db.ensure_current_view(table, key=key)
        logger.info("  view %s%s ready", table, db.CURRENT_SUFFIX)


if __name__ == "__main__":
    bootstrap()
