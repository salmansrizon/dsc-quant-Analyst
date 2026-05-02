# DSC Quant Analyst — Task Breakdown

> Each module is self-contained. Complete in order. Check box when done.

---

## Module 1: Backend Auth System
> JWT-based authentication with BigQuery user storage

- [ ] **1.1** Install deps: `pyjwt`, `bcrypt`, `python-multipart`
- [ ] **1.2** Create `backend/auth.py` — JWT token creation/verification helpers
- [ ] **1.3** Create `backend/models.py` — Pydantic schemas (UserCreate, UserLogin, UserResponse, TokenResponse)
- [ ] **1.4** Create `backend/user_service.py` — BigQuery CRUD for users table (create, get_by_email, get_by_id, list_all, update, delete)
- [ ] **1.5** Add auth endpoints to `api.py`:
  - `POST /api/auth/signup` (email, phone, password, full_name)
  - `POST /api/auth/login` (email + password → JWT)
  - `GET /api/auth/me` (JWT → user profile)
- [ ] **1.6** Add middleware: `get_current_user` dependency (extracts JWT from header)
- [ ] **1.7** Add role guard: `require_admin` dependency
- [ ] **1.8** Test auth flow locally with curl/httpie

---

## Module 2: Frontend Design System
> TradingView-inspired dark theme CSS tokens

- [ ] **2.1** Create `frontend/src/index.css` — CSS custom properties (colors, typography, spacing, radius)
- [ ] **2.2** Create `frontend/src/styles/components.css` — reusable component classes (buttons, cards, inputs, tables, badges)
- [ ] **2.3** Create `frontend/src/styles/layout.css` — sidebar, topbar, grid system
- [ ] **2.4** Create `frontend/src/styles/animations.css` — transitions, skeleton loaders, fade-in
- [ ] **2.5** Verify WCAG AA contrast on all token combinations

---

## Module 3: Frontend Auth Pages
> Login, Signup, and auth state management

- [ ] **3.1** Create `frontend/src/context/AuthContext.jsx` — React context for user state + JWT storage
- [ ] **3.2** Create `frontend/src/api/client.js` — fetch wrapper with base URL and JWT header injection
- [ ] **3.3** Create `frontend/src/pages/Login.jsx` — email + password form
- [ ] **3.4** Create `frontend/src/pages/Signup.jsx` — email, phone, password, full_name form
- [ ] **3.5** Create `frontend/src/components/ProtectedRoute.jsx` — redirect to login if no JWT
- [ ] **3.6** Create `frontend/src/components/AdminRoute.jsx` — redirect if not admin role
- [ ] **3.7** Wire up routing in `App.jsx` with protected routes

---

## Module 4: Dashboard Page
> Market overview with summary cards, gainers/losers, sector view

- [ ] **4.1** Create `frontend/src/pages/Dashboard.jsx` — main dashboard layout
- [ ] **4.2** Create `frontend/src/components/MarketSummaryCards.jsx` — total stocks, sectors, avg price, last updated
- [ ] **4.3** Create `frontend/src/components/TopMoversTable.jsx` — top gainers + losers tabs
- [ ] **4.4** Create `frontend/src/components/SectorPerformance.jsx` — sector cards with stock count, avg LTP, volume
- [ ] **4.5** Create `frontend/src/components/Sidebar.jsx` — navigation sidebar with role-based menu items
- [ ] **4.6** Create `frontend/src/components/Topbar.jsx` — user avatar, search, notifications bell

---

## Module 5: Symbol Profile Page
> Individual stock detail with price history and announcements

- [ ] **5.1** Create `frontend/src/pages/SymbolProfile.jsx` — stock detail page layout
- [ ] **5.2** Create `frontend/src/components/PriceChart.jsx` — line/candlestick chart (TradingView Lightweight Charts)
- [ ] **5.3** Create `frontend/src/components/StockInfoCard.jsx` — LTP, HIGH, LOW, VOLUME, TRADE, CLOSEP, YCP
- [ ] **5.4** Create `frontend/src/components/AnnouncementsList.jsx` — recent announcements for symbol
- [ ] **5.5** Add "Add to Watchlist" and "Add to Portfolio" action buttons
- [ ] **5.6** Install `lightweight-charts` npm package

---

## Module 6: Watchlist Feature
> Users can track favorite symbols

- [ ] **6.1** Add backend endpoints:
  - `GET /api/watchlist` — list user's watchlist with current prices
  - `POST /api/watchlist` — add symbol
  - `DELETE /api/watchlist/{symbol}` — remove symbol
- [ ] **6.2** Create `backend/watchlist_service.py` — BigQuery CRUD for watchlists table
- [ ] **6.3** Create `frontend/src/pages/Watchlist.jsx` — watchlist page with live prices
- [ ] **6.4** Create `frontend/src/components/WatchlistRow.jsx` — symbol row with price, change, remove button
- [ ] **6.5** Add watchlist toggle button to symbol profile page

---

## Module 7: Portfolio Feature
> Track holdings with P&L calculation

- [ ] **7.1** Add backend endpoints:
  - `GET /api/portfolio` — list user's portfolio with current values
  - `POST /api/portfolio` — add holding (symbol, buy_price, qty, buy_date, price_target, stop_loss)
  - `PUT /api/portfolio/{id}` — update holding
  - `DELETE /api/portfolio/{id}` — remove holding
  - `GET /api/portfolio/summary` — total invested, current value, total P&L
- [ ] **7.2** Create `backend/portfolio_service.py` — BigQuery CRUD + P&L calculations
- [ ] **7.3** Create `frontend/src/pages/Portfolio.jsx` — portfolio page layout
- [ ] **7.4** Create `frontend/src/components/PortfolioTable.jsx` — holdings table with P&L columns
- [ ] **7.5** Create `frontend/src/components/AddHoldingModal.jsx` — form modal
- [ ] **7.6** Create `frontend/src/components/PortfolioSummaryCards.jsx` — total invested, current value, P&L, best/worst performer

---

## Module 8: Price Alerts
> Set price targets, get notified when hit

- [ ] **8.1** Add backend endpoints:
  - `GET /api/alerts` — list user's alerts
  - `POST /api/alerts` — create alert (symbol, target_price, direction)
  - `DELETE /api/alerts/{id}` — remove alert
- [ ] **8.2** Create `backend/alert_service.py` — BigQuery CRUD for price_alerts table
- [ ] **8.3** Create `backend/alert_checker.py` — script that runs after scrape, checks alerts vs current prices, marks triggered
- [ ] **8.4** Create `frontend/src/components/AlertsPanel.jsx` — list + create alerts UI
- [ ] **8.5** Integrate alert checker into GitHub Actions workflow (runs after scrapers)

---

## Module 9: Admin Panel
> User management + pipeline monitoring

- [ ] **9.1** Add backend endpoints:
  - `GET /api/admin/users` — list all users
  - `PUT /api/admin/users/{id}` — update user role/status
  - `DELETE /api/admin/users/{id}` — remove user
  - `GET /api/admin/pipeline-status` — last scrape times from BigQuery updated_at
  - `GET /api/admin/logs` — read recent log files
- [ ] **9.2** Create `frontend/src/pages/AdminUsers.jsx` — user management table
- [ ] **9.3** Create `frontend/src/pages/AdminPipeline.jsx` — pipeline status dashboard
- [ ] **9.4** Create `frontend/src/components/UserEditModal.jsx` — edit user role/permissions
- [ ] **9.5** Create `frontend/src/components/LogViewer.jsx` — scrollable log output

---

## Module 10: Telegram Notifications
> Bot sends portfolio digest + price alerts

- [ ] **10.1** Create Telegram bot via @BotFather, save token
- [ ] **10.2** Install `python-telegram-bot` in backend
- [ ] **10.3** Create `backend/notifications/telegram_bot.py` — bot setup, `/start` command links user
- [ ] **10.4** Create `backend/notifications/telegram_service.py` — send message functions
- [ ] **10.5** Add backend endpoint: `POST /api/notifications/telegram/link` — user links Telegram chat_id
- [ ] **10.6** Create BigQuery table: `notification_preferences` (user_id, channel, chat_id, phone, enabled)
- [ ] **10.7** Create `backend/notifications/digest.py` — generates daily portfolio summary message
- [ ] **10.8** Create `backend/notifications/send_alerts.py` — sends triggered price alert messages
- [ ] **10.9** Add notification step to GitHub Actions workflow (runs after alert_checker)
- [ ] **10.10** Create `frontend/src/pages/NotificationSettings.jsx` — user toggles Telegram/WhatsApp

---

## Module 11: WhatsApp Config (Scaffold)
> Prep config for admin to enable later with Twilio

- [ ] **11.1** Create `backend/notifications/whatsapp_service.py` — Twilio WhatsApp send function (disabled by default)
- [ ] **11.2** Create `backend/notifications/whatsapp_config.py` — env var config: `TWILIO_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`
- [ ] **11.3** Add WhatsApp toggle to notification preferences table
- [ ] **11.4** Add setup instructions to README: how admin enables WhatsApp via Twilio
- [ ] **11.5** Add WhatsApp env vars to `.env.example`

---

## Module 12: Extra Features (v2)
> Optional enhancements after core is stable

- [ ] **12.1** Sector Heatmap — color-coded grid of sector performance
- [ ] **12.2** Stock Screener — filter by price range, volume, sector
- [ ] **12.3** Comparison Tool — overlay multiple symbols on one chart
- [ ] **12.4** Portfolio Analytics — pie chart allocation, diversification score
- [ ] **12.5** Export to CSV — download watchlist/portfolio
- [ ] **12.6** Dark/Light Mode Toggle
- [ ] **12.7** Smart Insights — unusual volume detection, 52-week high/low alerts

---

## Build Order

```
Module 1 (Auth) → Module 2 (Design) → Module 3 (Auth UI)
    ↓
Module 4 (Dashboard) → Module 5 (Symbol Profile)
    ↓
Module 6 (Watchlist) → Module 7 (Portfolio) → Module 8 (Alerts)
    ↓
Module 9 (Admin) → Module 10 (Telegram) → Module 11 (WhatsApp scaffold)
    ↓
Module 12 (Extras)
```

---

*Last updated: 2026-05-02*
