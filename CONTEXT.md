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

### Notifications
- **Telegram Alert**: Price alert notification delivered via Telegram bot
- **WhatsApp Alert**: Price alert notification delivered via WhatsApp (placeholder/ready)