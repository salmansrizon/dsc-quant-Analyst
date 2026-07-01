# Domain Context

## Glossary

### Stock Data
- **Symbol**: Ticker identifier for a stock (e.g. ABBANK) traded on the Dhaka Stock Exchange
- **Sector**: Industry classification (24 sectors: Bank, Cement, Engineering, etc.)
- **LTP**: Last Traded Price — the most recent price at which a stock was traded
- **Datamatrix**: Snapshot of all stocks with current prices, technical indicators, and fundamental data (414+ stocks, 34 columns). Stored in BigQuery table `lankabd_datamatrix`. Truncated and refreshed on each scrape.
- **Price Archive**: Historical daily OHLCV data for each symbol (~3 years, 716+ records per stock). Stored in BigQuery table `lankabd_price_archive`. Appended incrementally.
- **Announcement**: Corporate disclosures/news from companies. Stored in BigQuery table `lankabd_announcements`. Appended incrementally.

### Navigation
- **Stock Profile**: The detail page shown when a user clicks any Symbol anywhere in the app (tables, search, watchlist, and the DSEX/DSES/DS30 index tickers on the home page). Replaces the old StockDrawer slide-out. One page type for both individual companies and market indices — "index" in product conversation is used loosely to mean "whatever was clicked," not a separate page type.

### Users & Personalization
- **User**: Authenticated individual with email/password credentials, JWT-authenticated
- **Watchlist**: User-curated list of symbols tracked for quick reference
- **Portfolio**: User's holdings with buy price, quantity, buy date, and computed P&L
- **Price Alert**: User-defined threshold (above/below a target price) that triggers a notification
- **Role**: User classification — `user` or `admin` — controlling access to admin features

### Subscriptions & Pricing
- **Package**: An admin-defined, named, fixed-price notification subscription preset (e.g. "Starter", "Pro") with a fixed medium/alert_channel/digest_channel/alert_cap/digest_cadence configuration. Created via the admin Package Builder. Stored in BigQuery table `admin_bundles` (table not yet created in production). Selecting one applies its config directly and skips straight to payment — it is not a starting point for further editing.
- **Custom Subscription**: A user-built, à la carte notification subscription where the user picks medium/alert_channel/digest_channel/alert_cap/digest_cadence individually, priced by summing `pricing_weights` (table not yet created in production). Both Packages and Custom Subscriptions are submitted as rows in `subscription_packages` and go through the same pending → admin-approved/rejected lifecycle.

### Data Pipeline
- **BigQueryHelper**: Python class (`backend/utils/bigquery_helper.py`) that manages GCP BigQuery connections, uploads, and queries
- **Scrape**: Periodic fetch from lankabd.com, transform to DataFrame, upload to BigQuery
- **Incremental**: Price archive and announcements use `get_last_date()` to fetch only new records since last scrape
- **Truncate**: Datamatrix is fully replaced each scrape (snapshot, not history)

### Notifications
- **Telegram Alert**: Price alert notification delivered via Telegram bot
- **WhatsApp Alert**: Price alert notification delivered via WhatsApp (placeholder/ready)
- **Dispatch Scheduler**: The GitHub Actions cron that runs alert checking and digest dispatch, chained after the daily data pipeline, on its own workflow. Frequency is capped at once/day because `lankabd_datamatrix.LTP` only refreshes once/day — "decoupled" means independently schedulable from the data pipeline, not higher-frequency.
- **Digest**: A periodic summary notification (portfolio P&L + top gainers/losers) sent per a subscription's `digest_cadence` (daily/alternate/weekly), tracked via `last_digest_sent_at` on `subscription_packages`. Distinct from a Price Alert — a Digest is scheduled, a Price Alert is threshold-triggered.