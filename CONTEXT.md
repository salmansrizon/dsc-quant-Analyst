# Domain Context

## Glossary

### Stock Data
- **Symbol**: Ticker identifier for a stock (e.g. ABBANK) traded on the Dhaka Stock Exchange
- **Sector**: Industry classification (24 sectors: Bank, Cement, Engineering, etc.)
- **LTP**: Last Traded Price — the most recent price at which a stock was traded
- **Datamatrix**: Snapshot of all stocks with current prices, technical indicators, and fundamental data (414+ stocks, 34 columns). Stored in BigQuery table `lankabd_datamatrix`. Truncated and refreshed on each scrape.
- **Price Archive**: Historical daily OHLCV data for each symbol (~3 years, 716+ records per stock). Stored in BigQuery table `lankabd_price_archive`. Appended incrementally.
- **Announcement**: Corporate disclosures/news from companies. Stored in BigQuery table `lankabd_announcements`. Appended incrementally.
- **Corporate Action**: An event that changes a symbol's share structure — a **bonus** / **stock dividend** (extra shares) or a **split**. It drops the raw price with no real move, so indicators read a false crash unless adjusted.
- **Record Date**: The last cum-dividend trading day — the last day a bar still carries the pre-action price. Adjustment applies to bars with `Date <= record_date`. (lankabd exposes record_date, not the ex-date.)
- **Adjustment Factor**: The multiplier that makes a series continuous across a corporate action. A bonus of X% → `1/(1+X/100)`; a bar sees the product of every factor whose action is on or after it. Applied **on read** at the `price_series` seam (#63), never stored.

### Users & Personalization
- **User**: Authenticated individual with email/password credentials, JWT-authenticated
- **Watchlist**: User-curated list of symbols tracked for quick reference
- **Portfolio**: User's holdings with buy price, quantity, buy date, and computed P&L
- **Price Alert**: User-defined threshold (above/below a target price) that triggers a notification
- **Role**: User classification — `user` or `admin` — controlling access to admin features

### Data Pipeline
- **BigQueryHelper**: Python class (`backend/utils/bigquery_helper.py`) that manages GCP BigQuery connections, uploads, and queries
- **Scrape**: Periodic fetch from lankabd.com, transform to DataFrame, upload to BigQuery
- **Incremental**: Price archive and announcements use `get_last_date()` to fetch only new records since last scrape
- **Truncate**: Datamatrix is fully replaced each scrape (snapshot, not history)

### Navigation
- **Stock Profile / Stock Detail**: The detail page shown when a user clicks any Symbol (tables, search, watchlist, index tickers). On the trunk this is the `.tsx` `StockDetail` page (#36); main's `.jsx` `StockProfile` reconciles into it (#82). One page type for individual companies and market indices.

### Subscriptions & Pricing (#77)
- **Package (admin bundle)**: An admin-defined, named, fixed-price notification subscription preset — a fixed medium/alert_channel/digest_channel/alert_cap/digest_cadence config. Stored append-only in `admin_bundles`. Selecting one applies its config and skips to payment.
- **Custom Subscription**: A user-built à-la-carte subscription (pick medium/channels/cap/cadence individually), priced by summing `pricing_weights`. Both Packages and Custom Subscriptions land as rows in `subscription_packages` and go through the pending → admin-approved/rejected lifecycle. All three tables are append-only versions + `_current` views (ported off main's DML in #77).

### Notifications
- **Notification channels (#78)**: an alert crossing fans out to the owner's enabled channels — **email** (Resend), **Telegram**, **WhatsApp**, **web-push** — each with its own log-before-send (the `notifications` lock is keyed by alert_id+type+channel). Enabled channels + addresses live in `notification_preferences` (append-only, one row per user).
- **Dispatch Scheduler**: the cron that runs the alert sweep + digest dispatch. On the trunk the alert sweep is Vercel Cron → `POST /api/internal/run-alerts` (#66); reconciling main's GH-Actions dispatch is #80.
- **Digest**: a periodic summary notification (portfolio P&L + top movers) per a subscription's `digest_cadence`, tracked via `last_digest_sent_at` on `subscription_packages`. Distinct from a threshold-triggered alert.