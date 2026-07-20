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

# The append-only tables come from the shared registry (#62) — key + columns
# in one place, so this file and db.VERSIONED_TABLES can no longer drift.
try:
    from backend.schema import TABLES
except ImportError:  # standalone: cwd=backend
    from schema import TABLES


def _table_exists(name: str) -> bool:
    try:
        db.client().get_table(db.qualified_name(name))
        return True
    except Exception:
        return False


def _create_table(name: str, columns, spec=None) -> None:
    cols = ", ".join(f"{c} {t}" for c, t in columns)
    ddl = f"CREATE TABLE {db.table_id(name)} ({cols})"
    # Time-partitioned raw tables (#86): BigQuery expires old partitions itself.
    if spec is not None and spec.partition:
        ddl += f" PARTITION BY {spec.partition}"
        if spec.expiration_days:
            ddl += f" OPTIONS(partition_expiration_days={spec.expiration_days})"
    db.client().query(ddl).result()


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
    for table, spec in TABLES.items():
        columns, key = spec.columns, spec.key
        if not _table_exists(table):
            _create_table(table, columns, spec)
            logger.info("created table %s", table)
        else:
            added = _add_missing_columns(table, columns)
            if added:
                logger.info("added columns to %s: %s", table, ", ".join(added))
            else:
                logger.info("table %s already current", table)

        # Raw log tables (#86) are never superseded — no `_current` view.
        if getattr(spec, "versioned", True):
            db.ensure_current_view(table, key=key)
            logger.info("  view %s%s ready", table, db.CURRENT_SUFFIX)


if __name__ == "__main__":
    bootstrap()
