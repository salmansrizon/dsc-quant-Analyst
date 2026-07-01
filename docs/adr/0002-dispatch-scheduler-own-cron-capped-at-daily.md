# Notification dispatch gets its own cron, but stays capped at once/day

Alert checking and digest dispatch were going to be "decoupled" from the daily data pipeline so they could run on their own schedule. The obvious reading of that is "run more often." We rejected that: `lankabd_datamatrix.LTP` (what Price Alerts compare against) is only ever refreshed once a day by `daily_pipeline.yml` (`30 8 * * 0-4`), so checking alerts more frequently would just re-evaluate the same stale price repeatedly — no alert would fire any sooner.

We decided "decoupled" means *independently schedulable and retryable*, not higher-frequency: a new GitHub Actions workflow runs alert checking and digest dispatch chained together, scheduled a few minutes after the data pipeline, instead of being sequential steps inside `daily_pipeline.yml`. This keeps the dispatch job's success/failure and schedule separate from the scraper's, without pretending we have intraday price data we don't have.

If real-time alerting is wanted later, it requires sourcing intraday price data first — a separate, larger decision (same shape as the deferred index-data-source decision in ADR-0001).
