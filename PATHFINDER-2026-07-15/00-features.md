# Feature Inventory — backend

Scope of this audit: `backend/` data-access layer (not a full-repo feature map).

| Feature | Entry points | Core files | Purpose |
|---|---|---|---|
| Auth | `api.py` /api/auth/*, `auth.py:get_current_user` | auth.py, user_service.py, models.py | Signup/login/JWT; per-request identity |
| Market data (read) | `api.py` /api/market/* | bq_service.py (list_sectors/list_stocks/get_stock/price_history/technical_indicators/top_movers/market_summary), indicators.py | Read-only market + indicator queries |
| Watchlist | /api/watchlist | bq_service.py (get/add/remove) | User-owned symbol lists |
| Portfolio | /api/portfolio | bq_service.py (get/add/update/delete/summary) | Holdings + P&L |
| Alerts | /api/alerts | bq_service.py (get/create/delete), alert_checker.py | Price alerts + trigger check |
| Admin export | /api/admin/export/* | exports.py | CSV/JSON data export |
| ETL / scrapers | scripts | dataGrid.py, priceArchive.py, announcement.py, utils/bigquery_helper.py | Scrape lankabd.com → BigQuery |

**Cross-cutting concern audited:** BigQuery data access — spread across bq_service.py, user_service.py, exports.py, utils/bigquery_helper.py with four client bootstraps and four table-name helpers. See `02-duplication-report.md`.
