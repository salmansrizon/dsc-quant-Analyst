"""The append-only table registry (#62): one home for each versioned table's
key column and full column schema.

Formerly this was split — `db.VERSIONED_TABLES` (name -> key) and
`bootstrap_tables.SCHEMAS` (name -> columns) — two lists that had to agree and
drifted silently (a `SCHEMAS[table]` KeyError in a hand-run script was the only
alarm). Now there is one dict: `db.append_version` rejects any table not in it
(a typo used to append to an autodetect-created table with no `_current` view,
where the rows simply never read back), and `bootstrap_tables` creates exactly
these.

No dependencies on purpose, so both `db` and `bootstrap_tables` can import it
without a cycle (bootstrap imports db).
"""
from typing import NamedTuple

_TS = "TIMESTAMP"
_STR = "STRING"


class TableSpec(NamedTuple):
    key: str                              # column the latest version resolves per
    columns: tuple[tuple[str, str], ...]  # (name, BigQuery type)


TABLES: dict[str, TableSpec] = {
    "users": TableSpec("id", (
        ("id", _STR), ("email", _STR), ("phone", _STR), ("password_hash", _STR),
        ("full_name", _STR), ("role", _STR),
        # Bumped by password-reset and logout-all (#68); a refresh token's
        # token_version must match this. NULL on rows appended before it existed;
        # callers COALESCE it to 0, the documented default.
        ("token_version", "INT64"),
        ("created_at", _TS), ("updated_at", _TS), ("is_deleted", "BOOL"),
    )),
    "watchlists": TableSpec("id", (
        ("id", _STR), ("user_id", _STR), ("symbol", _STR),
        ("added_at", _TS), ("updated_at", _TS), ("is_deleted", "BOOL"),
    )),
    "portfolios": TableSpec("id", (
        ("id", _STR), ("user_id", _STR), ("symbol", _STR),
        ("buy_price", "FLOAT64"), ("quantity", "INT64"), ("buy_date", _STR),
        ("price_target", "FLOAT64"), ("stop_loss", "FLOAT64"), ("notes", _STR),
        ("created_at", _TS), ("updated_at", _TS), ("is_deleted", "BOOL"),
    )),
    "price_alerts": TableSpec("id", (
        ("id", _STR), ("user_id", _STR), ("symbol", _STR),
        ("target_price", "FLOAT64"), ("direction", _STR),
        ("is_triggered", "BOOL"), ("triggered_at", _TS),
        ("created_at", _TS), ("updated_at", _TS), ("is_deleted", "BOOL"),
    )),
    # Type-discriminated alerts (#66, from #34). `type` names the detector,
    # `condition_json` holds its per-type condition, so adding a type is data,
    # never an ALTER. `last_met` is the edge-trigger state; `is_active` the
    # one-shot flag. Supersedes `price_alerts` — see migrations/002.
    "alerts": TableSpec("id", (
        ("id", _STR), ("user_id", _STR), ("type", _STR), ("symbol", _STR),
        ("condition_json", _STR), ("last_met", "BOOL"), ("is_active", "BOOL"),
        ("created_at", _TS), ("updated_at", _TS), ("is_deleted", "BOOL"),
    )),
    # Delivery log (#66, from #34). `status` is the log-before-send lock.
    # Transactional email (#39 reset) logs here too, alert_id NULL.
    "notifications": TableSpec("id", (
        ("id", _STR), ("user_id", _STR), ("alert_id", _STR),
        ("channel", _STR), ("type", _STR), ("subject", _STR),
        ("status", _STR), ("attempts", "INT64"), ("error", _STR),
        ("created_at", _TS), ("updated_at", _TS), ("is_deleted", "BOOL"),
    )),
    # Reported fundamentals (#57). Grain: one row per symbol per reporting period.
    "fundamentals_earnings": TableSpec("id", (
        ("id", _STR), ("symbol", _STR), ("sector", _STR), ("year", "INT64"),
        ("period", _STR), ("period_raw", _STR),
        ("eps", "FLOAT64"), ("nav", "FLOAT64"),
        ("publish_date", "DATE"), ("source", _STR),
        ("updated_at", _TS), ("is_deleted", "BOOL"),
    )),
    # Financial ratios from the company API (#58). Long, not wide; `code` is
    # sector-scoped, so query a metric by `name`.
    "fundamentals_ratios": TableSpec("id", (
        ("id", _STR), ("symbol", _STR), ("year", "INT64"),
        ("code", _STR), ("name", _STR), ("category", _STR),
        ("result", "FLOAT64"), ("equation", _STR), ("base_equation", _STR),
        ("updated_at", _TS), ("is_deleted", "BOOL"),
    )),
    # Statement line items (#58). Grain: one row per symbol per year per line.
    "fundamentals_statements": TableSpec("id", (
        ("id", _STR), ("symbol", _STR), ("year", "INT64"),
        ("fs_type", _STR), ("fs_code", _STR), ("fs_key", _STR),
        ("fs_value", "FLOAT64"), ("fs_order", "INT64"),
        ("updated_at", _TS), ("is_deleted", "BOOL"),
    )),
    # One dividend DECLARATION (#57). A company declares several a year, so
    # symbol|year would collapse them.
    "fundamentals_dividends": TableSpec("id", (
        ("id", _STR), ("symbol", _STR), ("sector", _STR), ("year", "INT64"),
        ("dividend_type", _STR), ("dividend_type_raw", _STR),
        ("cash_dividend_pct", "FLOAT64"), ("stock_dividend_pct", "FLOAT64"),
        ("publish_date", "DATE"), ("record_date", "DATE"),
        ("agm_date", "DATE"), ("year_end_date", "DATE"), ("source", _STR),
        ("updated_at", _TS), ("is_deleted", "BOOL"),
    )),
}
