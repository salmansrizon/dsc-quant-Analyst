# Feature Inventory — backend/ (2026-07-16)

Audit scope: `backend/` only (2820 lines Python). Follows up `PATHFINDER-2026-07-15/`, which predates the
data-access cleanup cluster (#40/#41/#42/#43/#44).

## What changed since the 2026-07-15 audit

The prior audit's headline finding — **four independent BigQuery client bootstraps** — is **resolved**.
`bq_service.py` is gone; `db.py` is the single access point; all four API services do `from . import db`;
`BigQueryHelper` is a shim over `db.client()` (#44).

| Feature | Entry points | Core files | Purpose |
|---|---|---|---|
| BigQuery access kernel | `db.py:81 client()`, `:90 qualified_name`, `:99 table_id`, `:104 insert_rows`, `:119 execute_dml` | db.py | Single client bootstrap + credential resolution + DML. New (#41/#44) |
| Auth & identity | `api.py:31 signup`, `:41 login`, `:53 read_me`; `auth.py:57 get_current_user`, `:90 require_admin` | auth.py, user_service.py, models.py | JWT issue/verify; identity from claims (#42) |
| Market data (read) | `api.py:64-103` (7 routes) | market_service.py | Datamatrix / price-archive / announcement queries |
| Technical indicators | `market_service.py:101` → `indicators.py:346 compute_all` | indicators.py | On-read compute (#31). The only backend module with zero BigQuery coupling |
| Watchlist | `api.py:109-121` | watchlist_service.py | User symbol lists |
| Portfolio | `api.py:127-151` | portfolio_service.py | Holdings + P&L |
| Alerts (CRUD) | `api.py:157-169` | alerts_service.py | Alert records |
| **Alert triggering** | `alert_checker.py:65 __main__` → `:8 check_alerts` | alert_checker.py | Batch job. **Separate from alerts_service**, reaches BQ via BigQueryHelper |
| Admin & users | `api.py:175-193` | user_service.py | User admin |
| Admin export | `api.py:196-214` | exports.py | CSV/JSON export |
| **Sector snapshot ETL** | `dataGrid.py:227 __main__` → `:181 scrape_all_sectors` | dataGrid.py | Scrapes all sectors → `lankabd_datamatrix`, `truncate=True` (`:215`) |
| **Per-symbol incremental ETL** | `priceArchive.py:380 __main__` → `:192`; `announcement.py:428 __main__` → `:203` | priceArchive.py, announcement.py | Symbol fanout → `lankabd_price_archive` / `lankabd_announcements`; append + `get_last_date` |
| ETL BQ facade | `utils/bigquery_helper.py:26 BigQueryHelper` | bigquery_helper.py | Shim over `db.client()` (#44) |
| Operator scripts | `create_admin.py:42`, `upload_csvs.py:30`, `check_keys.py`, `check_citybank.py` | — | Loose CLI utilities |

## Scraper boundary: two features, not one or three

Decided on the import graph and a diff, not filenames:

- **No cross-imports.** `import dataGrid|priceArchive|announcement` returns nothing. Three independent
  `__main__` CLIs; no orchestrator exists (`workflows/`, `.github/` are empty).
- **dataGrid is the universe producer.** It alone writes `lankabd_datamatrix` with `truncate=True`. Both
  others call `get_symbols_from_sectors()` which *reads* `lankabd_datamatrix` (`announcement.py:54`,
  `priceArchive.py:57`) — a data-coupled producer→consumer edge, not an import edge.
- **announcement + priceArchive are one skeleton, two payloads.** `get_symbols_from_sectors`
  (announcement.py:50-64 vs priceArchive.py:53-67) is **byte-identical**; `get_session` differs only by a
  docstring. Same 4-function shape, same `by_symbol`/`by_sector` variants, same `get_last_date`-driven
  incremental append. dataGrid has no `get_date_range`, no `get_last_date`, no symbol fanout — genuinely
  different shape.

## Residual observations (describing, not proposing)

- `alert_checker.py:52-58` builds `sql_update` by f-string-interpolating `triggered_ids` — the only
  unparameterized DML in the backend, and it bypasses `db.execute_dml` entirely. Ids are server-generated
  `uuid4` (`alerts_service.py:28`), so it is not exploitable today.
- `exports.py:14 _get_bigquery_client` survives as a wrapper around `db.client()`.
- `create_admin.py:4` uses a bare `from user_service import` — only runs with cwd=backend.
- Tests exist for db / auth / indicators / mutations / exports, but **none for any scraper**.

## Confidence

**High** on API/service boundaries and the scraper verdict (import graph + diff verified).
**Medium** on ETL run order: no scheduler found anywhere, so "dataGrid first" is inferred from the data
dependency alone.
