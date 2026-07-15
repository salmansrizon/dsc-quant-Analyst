# Handoff Prompts (`/make-plan`)

## System 0 — Kill truncate-and-reload (CRITICAL)

```
/make-plan Replace the truncate-and-reload mutation pattern in backend/bq_service.py with row-level BigQuery DML. Delete _rewrite_table (bq_service.py:37). Rewrite these to parameterized UPDATE/DELETE statements scoped by user_id: remove_from_watchlist (242), update_portfolio (298), delete_portfolio (320), delete_alert (385). Keep _insert_rows (WRITE_APPEND) for adds. This is a correctness fix: WRITE_TRUNCATE currently replaces the whole table with one user's rows, destroying every other user's data. Add a regression test that two users' watchlists survive one user's delete. Anti-patterns to avoid: do not add an ORM, do not read the whole table first, do not keep _rewrite_table behind a flag.
```

## System 1 — One BigQuery client + table helper

```
/make-plan Create backend/db.py with a single lazily-constructed BigQuery client() and one table_id(name) helper, moving the service-account credential resolution currently in backend/utils/bigquery_helper.py:14-32 into it. Replace the four bootstraps: bq_service.py:15, user_service.py:13 (also un-hardcode its PROJECT/DATASET), exports.py:16 (_get_bigquery_client), and BigQueryHelper in utils/bigquery_helper.py. Delete the three duplicate table-name helpers (_full_id, _uid, exports._get_full_table_id) in favor of db.table_id. Anti-patterns: no factory/registry — one module-level function; no per-call client construction.
```

## System 2 — Cache per-request auth

```
/make-plan Stop hitting BigQuery on every authenticated request. backend/auth.py:52 get_current_user calls user_service.get_user_by_id (user_service.py:83) per request. Embed email + role as JWT claims at issue time (create_access_token) and read them from the decoded token in get_current_user; only fall back to a DB lookup when a fresh record is required. No Redis. Add a test that an authenticated request makes zero BigQuery calls for identity.
```

## System 3 — Split the god module (after 0–2)

```
/make-plan Split backend/bq_service.py into market_service, watchlist_service, portfolio_service, alerts_service, each importing backend/db.py. Pure mechanical move — no behavior change. Update imports in backend/api.py. Do this only after backend/db.py (System 1) and the DML fix (System 0) have landed.
```
