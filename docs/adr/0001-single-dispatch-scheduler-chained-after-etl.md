# One scheduler: the alert/digest sweep is a step chained after the market ETL

Ticket #80. Two orchestration models had accreted on the two branches and had
to collapse into one:

- **staging (#66):** the edge-trigger alert sweep runs behind
  `POST /api/internal/run-alerts`, triggered by a **Vercel Cron** at a fixed
  `0 10 * * *`.
- **main (PRD-14, ADR-0002):** a **GitHub Actions** workflow (`dispatch_scheduler.yml`)
  runs `alert_checker` then `digest_dispatcher`, on its own cron a few minutes
  after `daily_pipeline.yml`.

## Decision

**The sweep runs as a step chained onto the end of `etl-market.yml`, on the
GitHub Actions runner. The Vercel Cron is retired.**

Concretely: after `dataGrid → priceArchive → announcement`, the same job runs
`python -m backend.alert_checker` (its own documented scale-out entry point),
and — when the Phase-3 dispatcher lands — a digest step after it. The
`/api/internal/run-alerts` endpoint stays, but only for manual / backfill runs.

## Why chained-after, not a separate timed cron

`lankabd_datamatrix.LTP` — what Price Alerts compare against — is refreshed
**exactly once a day, by this ETL**. Everything follows from that:

1. **A fixed-time trigger races the scrape.** The Vercel Cron fired at 10:00
   UTC; the ETL starts at 09:30 and a per-symbol scrape has no fixed duration.
   A slow or retried scrape means the sweep reads *yesterday's* LTP. Chaining
   the sweep as a step makes it run on the scrape's actual completion — the
   crossing is always evaluated against the price that just landed.
2. **No higher frequency is useful** (main's ADR-0002 reasoning, kept): checking
   more often than LTP refreshes just re-evaluates a stale price. "Decoupled"
   was only ever about independent success/failure, which a `continue-on-error`
   step already gives us — a delivery failure doesn't turn the ETL red, and the
   next day's sweep retries the still-active alert (the #48 no-consume guarantee).
3. **One engine, the tested one.** The sweep is staging's #66/#78 edge-trigger
   engine (`alert_checker.check_alerts` + `build_notifier`), *not* main's
   parallel `alert_checker`. The GH Actions entry runs that exact code
   unchanged — this is the scale-out its own docstring already documented, now
   realized. main's `dispatch_scheduler.yml` / `digest_dispatcher.py` /
   `daily_pipeline.yml` are superseded and not ported.

## Where the digest runs

Same chain, as the final step, after the alert sweep. Staging has the
subscription substrate for it (`subscriptions_service`: `digest_channel`,
`digest_cadence`, `last_digest_sent_at`) but no dispatcher yet — that is
Phase-3 work, out of this ticket. This ADR fixes its *placement* so the
Phase-3 build only adds one step, not a new schedule.

## Consequences

- `vercel.json` loses its `crons` array. The Vercel deploy no longer needs a
  scheduler; `CRON_SECRET` still guards the manual endpoint.
- The alert step needs `RESEND_API_KEY` (and any channel secrets) on the runner,
  alongside the `GCP_SERVICE_ACCOUNT_JSON` the ETL already has.
- If real-time alerting is ever wanted, it needs an intraday price source first
  — a separate, larger decision (unchanged from main's ADR-0002).
