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
    # Raw, immutable, time-partitioned tables (#86 behaviour_events) set these:
    # BigQuery drops partitions older than `expiration_days` itself — a storage
    # lifecycle, not a DELETE (the free tier forbids DML). `versioned=False`
    # skips the append-only `_current` view (these rows are never superseded).
    partition: str | None = None          # DATE/TIMESTAMP column to partition by
    expiration_days: int | None = None    # partition auto-expiry window
    versioned: bool = True                # False = raw log, no _current view


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
    # Per-user notification channel preferences (#78, ported from main). One row
    # per user (id = user_id), append-versioned; channels_enabled is a JSON
    # array string. main mutated this with UPDATE DML.
    "notification_preferences": TableSpec("id", (
        ("id", _STR), ("user_id", _STR),
        ("telegram_chat_id", _STR), ("whatsapp_number", _STR), ("email", _STR),
        ("web_push_subscription", _STR), ("channels_enabled", _STR),
        ("updated_at", _TS), ("is_deleted", "BOOL"),
    )),
    # Subscription packages (#77, ported from main). A user's à-la-carte or
    # bundle-based notification subscription, pending -> admin-approved/rejected.
    # main mutated these with UPDATE DML (403 on the free tier); here they are
    # append-only versions like everything else.
    "subscription_packages": TableSpec("id", (
        ("id", _STR), ("user_id", _STR),
        ("medium", "ARRAY<STRING>"),
        ("alert_channel", "BOOL"), ("digest_channel", "BOOL"),
        ("alert_cap", "INT64"), ("digest_cadence", _STR),
        ("bundle_id", _STR), ("status", _STR),           # pending|active|rejected
        ("transaction_id", _STR), ("submitted_at", _TS),
        ("decided_at", _TS), ("decided_by", _STR),
        ("last_digest_sent_at", _TS),
        ("created_at", _TS), ("updated_at", _TS), ("is_deleted", "BOOL"),
    )),
    # Admin-defined bundle presets (#77). main's update/deactivate used
    # read-all + WRITE_TRUNCATE (the #40 data-loss pattern) — now db.revise.
    "admin_bundles": TableSpec("id", (
        ("id", _STR), ("name", _STR),
        ("medium", "ARRAY<STRING>"),
        ("alert_channel", "BOOL"), ("digest_channel", "BOOL"),
        ("alert_cap", "INT64"), ("digest_cadence", _STR),
        ("price", "FLOAT64"), ("is_active", "BOOL"),
        ("created_by", _STR),
        ("created_at", _TS), ("updated_at", _TS), ("is_deleted", "BOOL"),
    )),
    # Pricing lookup for the custom-subscription estimator (#77). A static seed
    # table; id = dimension|key so it fits the append-only/_current shape.
    "pricing_weights": TableSpec("id", (
        ("id", _STR), ("dimension", _STR), ("key", _STR),
        ("weight_price", "FLOAT64"),
        ("updated_at", _TS), ("is_deleted", "BOOL"),
    )),
    # Rights issues from /Home/RightArchive (#65). Ingest-only for now — the v2
    # ex-rights price adjustment (needs the theoretical ex-rights value, more
    # than a single factor) is deferred (#33). Grain: one rights issue.
    "rights_archive": TableSpec("id", (
        ("id", _STR),                      # symbol|record_date
        ("symbol", _STR),
        ("right_offer", _STR),             # raw "1R:2"
        ("offer_new", "INT64"), ("offer_held", "INT64"),  # 1 new per 2 held
        ("issue_price", "FLOAT64"), ("right_premium", "FLOAT64"),
        ("record_date", "DATE"), ("year", "INT64"),
        ("subscription_open", "DATE"), ("subscription_close", "DATE"),
        ("source", _STR),
        ("updated_at", _TS), ("is_deleted", "BOOL"),
    )),
    # Investor profile (#85, personalization spine #84). One row per user
    # (id = user_id), append-versioned — an edit is a new version, the `_current`
    # view resolves the latest. `sector_prefs` is a JSON rank-ordered array
    # string ([0] = top choice); the #88 fit engine derives weights from rank.
    # `is_default` marks the neutral cold-start object (never user-set), which is
    # what the nudge banner keys on.
    "investor_profiles": TableSpec("id", (
        ("id", _STR), ("user_id", _STR),
        ("goal", _STR),          # income|growth|preservation
        ("risk", _STR),          # low|med|high
        ("horizon", _STR),       # short|medium|long
        ("sector_prefs", _STR),  # JSON rank-ordered array
        ("is_default", "BOOL"),
        ("updated_at", _TS), ("is_deleted", "BOOL"),
    )),
    # Raw behaviour events (#86, spine #84). Immutable facts that age out: BQ
    # drops partitions older than 8 days itself (7-day window + a day of slack
    # for a late rollup), so no DELETE is ever issued. Not versioned — an event
    # is never revised. `payload` holds type-specific detail (screener filters);
    # symbol/sector are promoted out so the rollup is plain GROUP BY, not JSON.
    "behaviour_events": TableSpec("id", (
        ("id", _STR), ("user_id", _STR), ("event_type", _STR),
        ("symbol", _STR), ("sector", _STR), ("payload", _STR),
        ("event_date", "DATE"), ("created_at", _TS),
    ), partition="event_date", expiration_days=8, versioned=False),
    # Per-user interest summary (#86). Rolled up daily from the 7-day event
    # window + standing portfolio/watchlist state. Append-only versions +
    # `_current`; `interest` is the 0..1 affinity #88/#93/#96 consume.
    "behaviour_summary": TableSpec("id", (
        ("id", _STR),                      # user_id|kind|key
        ("user_id", _STR), ("kind", _STR), ("key", _STR),
        ("interest", "FLOAT64"), ("event_count", "INT64"),
        ("last_event_at", _TS),
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
