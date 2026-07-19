# Duplication & Architecture Report — backend data access

_Evidence gathered by two discovery subagents; every claim cites ≥2 `file:line`._

## CRITICAL — not duplication, a correctness bug (surfaced during the audit)

**`_rewrite_table` truncate-and-reload destroys other users' data.**
Mutations read only the acting user's rows (`SELECT * ... WHERE user_id = @uid`) then call `_rewrite_table`, which uses `WRITE_TRUNCATE` (`bq_service.py:44`) — this **replaces the entire physical table** with just that one user's rows.

- `remove_from_watchlist` — `bq_service.py:242` (reads `WHERE uid` L243-248 → truncate L256)
- `update_portfolio` — `bq_service.py:298` (L299-304 → L316)
- `delete_portfolio` — `bq_service.py:320` (L321-326 → L333)
- `delete_alert` — `bq_service.py:385` (L386-391 → L393)

Result: as soon as there are ≥2 users, any one user editing their watchlist/portfolio/alerts **wipes every other user's rows** in that table. Plus a window where the table is empty (truncate before load commits), and last-writer-wins even for a single user. No transaction/lock exists anywhere in the file.

## Duplication 1 — four BigQuery client bootstraps

No shared factory. Four independent `bigquery.Client(...)` constructions:

- `bq_service.py:15` — `bigquery.Client(project=PROJECT)`, env-driven (`BIGQUERY_PROJECT_ID`/`BIGQUERY_DATASET_ID`, L12-13), ambient ADC.
- `user_service.py:13` — `bigquery.Client(project=PROJECT)`, **PROJECT/DATASET hardcoded** (L11-12), not env-driven.
- `exports.py:16` — `_get_bigquery_client()` builds a fresh client per export (uncached), env-driven.
- `utils/bigquery_helper.py:60` — `BigQueryHelper.__init__`; the **only** one that resolves service-account credentials (`GCP_SERVICE_ACCOUNT_JSON` → temp file → `GOOGLE_APPLICATION_CREDENTIALS`, L14-32). Used by `alert_checker.py:9`.

Three of four rely on ambient ADC populated by whichever co-imported module ran the credential setup first — an import-ordering dependency.

## Duplication 2 — table-name helper repeated 4×, 3 quoting conventions

- `bq_service._full_id` (`bq_service.py:17-18`) — backtick `` `proj.ds.table` ``
- `user_service._uid` (`user_service.py:15-16`) — backtick, identical shape
- `exports._get_full_table_id` (`exports.py:106-111`) — single-quote `'proj.ds.table'`, then re-wrapped in backticks at call site (L92-93)
- `bigquery_helper._get_full_table_id` (`utils/bigquery_helper.py:79-80`) — unquoted `proj.ds.table`

## Duplication 3 — per-request BigQuery auth lookup (no cache)

`auth.get_current_user` (`auth.py:48-55`) decodes the JWT then calls `user_service.get_user_by_id` (`user_service.py:83-102`), which runs a live `SELECT ... FROM users WHERE id=@uid` on **every authenticated request**. No caching → one BQ query per API call (cost + latency at scale).

## God module

`bq_service.py` (409 lines) owns market reads, watchlist, portfolio, alerts, and market-summary queries **and** all their mutations — Divergent Change (changes for many unrelated reasons).
