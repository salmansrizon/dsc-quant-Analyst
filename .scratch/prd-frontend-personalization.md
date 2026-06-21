# PRD: Interactive Market Dashboard & User Personalization

## Problem Statement

The DSC Quant Analyst project has a fully functional BigQuery data pipeline — stock datamatrix (415 symbols), price archives (847k+ records), and announcements (13k+ records) are all being scraped and stored — but there is no user interface to view, explore, or interact with this data. The `src/` directory is empty. Users have no way to see sector performance, browse stocks, track a watchlist, manage a portfolio, or set price alerts.

The backend API currently exposes only auth endpoints (`signup`, `login`, `me`) with an in-memory user store. There are no data endpoints for the frontend to consume. The `src/` frontend directory is completely empty — despite React 19, Recharts, React Router, and Lucide being installed.

## Solution

Build a complete React frontend with two feature areas:

1. **Market Dashboard** — an authenticated landing page showing sector summaries, top gainers/losers, a full stock table with search/filter, and individual symbol profile pages with price charts and announcements.

2. **User Personalization** — watchlist management, portfolio tracking with P&L, and price alerts, all persisted to BigQuery.

The backend will be extended with new REST endpoints (market data, watchlist CRUD, portfolio CRUD, alert CRUD, admin user management) and the user store will be migrated from in-memory to BigQuery persistence.

## User Stories

1. As a visitor, I want to see a live market dashboard with sector statistics (stock count, avg price, total volume), so that I can quickly gauge market health at a glance.
2. As a visitor, I want to view top gainers and losers, so that I can identify which stocks are moving.
3. As a visitor, I want to filter stocks by sector, so that I can focus on companies in a specific industry.
4. As a visitor, I want to search stocks by symbol or name, so that I can quickly find a specific company.
5. As a visitor, I want to click a stock symbol and see its detail page with current price, change, and key metrics, so that I can evaluate a single stock.
6. As a visitor, I want to see an interactive price chart (line chart) for any symbol with configurable time range, so that I can visualize price trends.
7. As a visitor, I want to see recent announcements for any symbol, so that I can stay informed about corporate events.
8. As a user, I want to sign up with email and password, so that I can access personalized features.
9. As a user, I want to log in and stay authenticated across page refreshes, so that I don't have to re-enter credentials.
10. As a user, I want to add symbols to my watchlist, so that I can track stocks I care about.
11. As a user, I want to see my watchlist with live prices and changes, so that I can monitor my tracked stocks in one place.
12. As a user, I want to remove symbols from my watchlist, so that I can keep it relevant.
13. As a user, I want to add holdings to my portfolio (symbol, buy price, quantity, buy date, price target, stop loss, notes), so that I can track my investments.
14. As a user, I want to see my portfolio with computed P&L (current value vs invested), so that I know how my investments are performing.
15. As a user, I want to see a portfolio summary card (total invested, current value, total P&L, avg P&L %), so that I can assess my overall position at a glance.
16. As a user, I want to edit or delete portfolio holdings, so that I can keep my records accurate.
17. As a user, I want to create price alerts for any symbol with a target price and direction (above/below), so that I get notified when a stock hits my target.
18. As a user, I want to see a list of my active alerts with current prices, so that I can monitor my pending triggers.
19. As a user, I want to delete alerts that are no longer relevant, so that I don't get unnecessary notifications.
20. As an admin, I want to view all users and their roles, so that I can manage the user base.
21. As an admin, I want to update user roles (promote to admin, demote to user), so that I can control access.
22. As an admin, I want to delete users, so that I can remove inactive or unauthorized accounts.
23. As a developer, I want server-side pagination on the stock list, so that the frontend loads quickly even with 415+ symbols.
24. As a developer, I want all BigQuery operations to work on the free tier (no DML), so that there is no billing required to run the app.

## Implementation Decisions

### Backend: New Modules

1. **`backend/bq_service.py`** — BigQuery read/write service (already built). Contains all query methods for market data, watchlists, portfolios, and alerts. Uses SELECT queries for reads and `load_table_from_dataframe` with WRITE_APPEND/WRITE_TRUNCATE for writes (free tier eligible). No DML SQL.

2. **`backend/user_service.py`** (rewritten) — Migrated from in-memory dict to BigQuery persistence. Uses `load_table_from_dataframe` for user signup. Read-modify-rewrite pattern for admin updates and deletes.

3. **`backend/api.py`** (extended) — Added ~20 new endpoints across four groups:
   - **Market Data** (no auth required): `GET /api/market/summary`, `/api/market/sectors`, `/api/market/stocks`, `/api/market/stocks/{symbol}`, `/api/market/top-movers`, `/api/market/price-history/{symbol}`, `/api/market/announcements`
   - **Watchlist** (auth required): `GET/POST /api/watchlist`, `DELETE /api/watchlist/{symbol}`
   - **Portfolio** (auth required): `GET /api/portfolio`, `GET /api/portfolio/summary`, `POST /api/portfolio`, `PUT /api/portfolio/{id}`, `DELETE /api/portfolio/{id}`
   - **Alerts** (auth required): `GET/POST /api/alerts`, `DELETE /api/alerts/{id}`
   - **Admin** (admin role required): `GET /api/admin/users`, `PUT /api/admin/users/{id}`, `DELETE /api/admin/users/{id}`

### Backend: Key API Contracts

**GET /api/market/stocks** — Query params: `sector` (optional), `search` (optional), `limit` (default 500). Returns array of `{Symbol, Sector, LTP, ChangePct, Volume_Qty_, ...}`.

**GET /api/market/price-history/{symbol}** — Query params: `days` (default 365, max 1095). Returns array of `{Date, Symbol, LTP, High, Low, Open, Close, Volume, SMA_20, RSI}`.

**POST /api/portfolio** — Body: `{symbol, buy_price, quantity, buy_date?, price_target?, stop_loss?, notes?}`. Returns `{id, symbol}`.

**GET /api/portfolio** — Returns array of `{id, symbol, buy_price, quantity, buy_date, current_price, pnl, pnl_percent}`.

**POST /api/alerts** — Body: `{symbol, target_price, direction}` where direction is `"above"` | `"below"`. Returns `{id, symbol}`.

### BigQuery Free Tier Strategy

SELECT queries work on the free tier. DML (INSERT/UPDATE/DELETE) does not. All write operations use `bigquery.Client.load_table_from_dataframe()` with the appropriate write disposition:
- **Inserts**: `WRITE_APPEND` — appends a single-row DataFrame to the table
- **Soft-deletes / Updates**: Read all rows, modify in-memory, rewrite entire small table with `WRITE_TRUNCATE`

This is feasible because user-specific tables (watchlists, portfolios, price_alerts, users) are small (fewer than 10k rows).

### Frontend Architecture

- **Routing**: React Router v7 with protected routes
- **Auth**: JWT stored in `AuthContext` (React Context), persisted to `localStorage`. API client injects `Authorization: Bearer` header.
- **Layout**: Sidebar navigation (collapsible) + Topbar with search and user menu. Dark theme (TradingView-inspired).
- **Charts**: Recharts for price line charts.
- **Icons**: Lucide.
- **API client**: Shared `api/client.js` wrapping `fetch()` with base URL and JWT injection.

### Frontend Page Map

| Route | Page | Auth | Description |
|-------|------|------|-------------|
| `/login` | Login | No | Email + password form |
| `/signup` | Signup | No | Registration form |
| `/` | Dashboard | Yes | Market overview, sector cards, top movers, stock table |
| `/symbol/:id` | SymbolProfile | Yes | Price chart, stock info, announcements, add-to-watchlist |
| `/watchlist` | Watchlist | Yes | User's saved symbols with live prices |
| `/portfolio` | Portfolio | Yes | Holdings table + summary cards |
| `/alerts` | Alerts | Yes | Price alert CRUD |
| `/admin/users` | AdminUsers | Admin | User management table |
| `/admin/pipeline` | AdminPipeline | Admin | Pipeline status dashboard |

### Frontend Component Tree

```
App
├── AuthContext.Provider
│   ├── Login / Signup
│   └── ProtectedRoute
│       └── Layout (Sidebar + Topbar)
│           ├── Dashboard
│           │   ├── MarketSummaryCards
│           │   ├── SectorPerformance
│           │   ├── TopMoversTable
│           │   └── StocksTable (search/filter)
│           ├── SymbolProfile
│           │   ├── StockInfoCard
│           │   ├── PriceChart (Recharts)
│           │   └── AnnouncementsList
│           ├── Watchlist
│           │   └── WatchlistRow[]
│           ├── Portfolio
│           │   ├── PortfolioSummaryCards
│           │   ├── PortfolioTable
│           │   └── AddHoldingModal
│           ├── Alerts
│           │   └── AlertsPanel
│           └── Admin
│               ├── AdminUsers (UserEditModal)
│               └── AdminPipeline (LogViewer)
```

## Testing Decisions

- **What makes a good test**: Test external behavior via API contracts, not implementation details. For the backend, test that endpoints return the correct status codes, shapes, and data. For the frontend, test that pages render the correct components and API calls succeed.
- **Backend seam**: Test via the FastAPI `TestClient` — start the app, call endpoints, assert responses. This is the highest seam that exercises routing, dependency injection, and business logic together.
- **Frontend seam**: Test via React Testing Library — render pages with mocked API responses, assert that the correct data appears in the DOM.
- **Prior art**: No existing tests in the codebase. A single `TestClient`-based integration test file for the API will serve as the pattern.
- **Specific test cases**:
  - `test_market_summary_returns_correct_shape`
  - `test_stock_detail_returns_404_for_unknown_symbol`
  - `test_watchlist_add_requires_auth`
  - `test_portfolio_pnl_computation_is_correct`
  - `test_admin_ping_requires_admin_role`
  - `test_signup_creates_user_in_bigquery`
  - `test_duplicate_email_returns_400`

## Out of Scope

- Real-time WebSocket price updates (the data is scraped, not streamed)
- Notification delivery (Telegram/WhatsApp integration) — the `alert_checker.py` already exists but notification dispatch is a separate feature
- Automated daily scrape via GitHub Actions (CI/CD pipeline is empty)
- Mobile responsive design (targeting desktop-first MVP)
- Dark/light mode toggle
- Stock screener with advanced filters
- Sector heatmap visualization
- CSV export from the frontend
- Password reset flow
- OAuth/social login

## Further Notes

- The BigQuery project `dbt-test-420614` does not have billing enabled, which means DML queries will fail. All write operations must use load jobs (`load_table_from_dataframe`) which are free-tier eligible.
- The existing GCP service account key file is at `backend/utils/dbt-test-420614-66e1946444d6.json`. A symlink at `dbt-test-420614-6c3337b4e737.json` points to it for backward compatibility with the legacy `bigquery_helper.py`.
- The `.env` file has been created at the project root with `BIGQUERY_PROJECT_ID`, `BIGQUERY_DATASET_ID`, and `GOOGLE_APPLICATION_CREDENTIALS`.
- The `index.html` entry point and Vite proxy (`/api` → `localhost:8000`) are already configured.
- The existing user `admin@dscquant.com` (password: `admin123`) exists in the BigQuery `users` table with role `admin`.
- The `CONTEXT.md` glossary has been created; it should be updated as new domain terms are resolved.
- `backend/utils/bigquery_helper.py` and `backend/utils/logger.py` were restored from git commit `5b5b470` and are available for the scraper scripts to use.