# Home page and Stock Profile redesign scoped to data already in BigQuery

The reference mockups (DSE-style market dashboard for the home page, full company-detail page for the Stock Profile) include widgets and tabs that need data we don't currently scrape:

- **Home page**: a DSEX/DSES/DS30 index time series, index-constituent weights (for "Index Contributor" rankings), circuit-breaker limits, spot/block trade feeds, and external economic/exchange-rate data.
- **Stock Profile**: Cash Flow, P&L, Balance Sheet, and Dividend History tabs, company contact info (PABX/email/address/website), and quarterly EPS (Q1/Q2/Q3/Annual).

None of this exists in `lankabd_datamatrix`, `lankabd_price_archive`, or `lankabd_announcements`. Sourcing it means new scrapers (per-company detail pages on lankabd.com for the profile data; a separate index-level target for DSEX/DSES/DS30) and new BigQuery tables/schema.

We decided to build both pages using only data we already have, and explicitly defer the unsourced widgets/tabs as backlog rather than build them with placeholder or fabricated data. The Home page "Sentiment" gauge is deferred for the same reason plus an additional one — there's no defined formula for it, so showing a number would misrepresent it as real market sentiment rather than an invented metric.

MACD(12,26,9) and Stochastic(14,3,3) on the home page are the one exception to "existing data only": the raw OHLC needed to compute them already exists in `lankabd_price_archive`, so they're in scope even though they're not pre-computed today. The Stock Profile's EMA20/50/100/200 and key-level summary are in scope for the same reason.
