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
    # Reported fundamentals (#57). Grain: one row per symbol per reporting
    # period. Fed by both DividendArchive (annual, 12y of history) and
    # GetLatestEarnings (current period).
    "fundamentals_earnings": [
        ("id", _STR),           # symbol|year|period
        ("symbol", _STR), ("sector", _STR),
        ("year", "INT64"),
        ("period", _STR),       # ANNUAL | H1 | Q1 | Q2 | Q3 | 9M | UNKNOWN
        ("period_raw", _STR),   # what the site said, to audit the mapping
        ("eps", "FLOAT64"), ("nav", "FLOAT64"),
        ("publish_date", "DATE"),
        ("source", _STR),       # dividend_archive | latest_earnings
        ("updated_at", _TS), ("is_deleted", "BOOL"),
    ],
    # Financial ratios from the company API (#58). Grain: one row per symbol per
    # year per ratio. LONG, not wide: the ratio set varies by sector (GP reports
    # 69, AB Bank 33), so a column per ratio means a migration every time
    # lankabd adds one — and #51 was that pain.
    "fundamentals_ratios": [
        ("id", _STR),           # symbol|year|code
        ("symbol", _STR), ("year", "INT64"),
        ("code", _STR),         # RTAMAQ0210 — stable machine key
        ("name", _STR), ("category", _STR),
        ("result", "FLOAT64"),
        ("equation", _STR),        # "158057490000.0000 / 191322941000.0000"
        ("base_equation", _STR),   # "ISTEX90000 / BS96033" — joins to fs_code
        ("updated_at", _TS), ("is_deleted", "BOOL"),
    ],
    # Statement line items (#58). Grain: one row per symbol per year per line.
    "fundamentals_statements": [
        ("id", _STR),           # symbol|year|fs_code
        ("symbol", _STR), ("year", "INT64"),
        ("fs_type", _STR),      # Balance Sheet | Income Statement | Cash Flow Statement
        ("fs_code", _STR),      # BS96002 — what a ratio's base_equation references
        ("fs_key", _STR),       # "Property Plant & Equipment"
        ("fs_value", "FLOAT64"),
        ("fs_order", "INT64"),
        ("updated_at", _TS), ("is_deleted", "BOOL"),
    ],
    # Grain: one dividend DECLARATION. A company declares several a year
    # (MARICO 2026 has five), so symbol|year would collapse them.
    "fundamentals_dividends": [
        ("id", _STR),           # symbol|year|type|publish_date
        ("symbol", _STR), ("sector", _STR),
        ("year", "INT64"),
        ("dividend_type", _STR),      # ANNUAL | SEMI_ANNUAL | INTERIM | FINAL | UNKNOWN
        ("dividend_type_raw", _STR),  # 754 rows are blank; some say "Annuall"
        ("cash_dividend_pct", "FLOAT64"), ("stock_dividend_pct", "FLOAT64"),
        ("publish_date", "DATE"), ("record_date", "DATE"),
        ("agm_date", "DATE"), ("year_end_date", "DATE"),
        ("source", _STR),
        ("updated_at", _TS), ("is_deleted", "BOOL"),
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
