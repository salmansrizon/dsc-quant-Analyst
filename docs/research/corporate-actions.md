# Corporate-action data & price-adjustment strategy — research findings (#33)

Date: 2026-07-18. Everything below was probed live against lankabd.com and our BigQuery.

## The problem is real — proven, not assumed

`lankabd_price_archive` stores **raw, unadjusted** OHLC (confirmed: no `adjusted_*`,
`split`, or `bonus` column in its 37-column schema). Indicators (#31) are computed
from those raw closes. A stock dividend halves the price overnight with no real
move, and every indicator reads it as a crash.

**EASTRNLUB, 50% stock dividend, record date 2025-12-22:**

```
2025/12/22  close 2501.5    ← last cum-dividend day
2025/12/23  close 1719.9   (-31.2%)   ← ex-day. 2501.5 / 1.5 = 1667.7; the rest is real move
```

To a 14-day RSI that -31% bar reads as deeply oversold; MACD flags a large bearish
cross. None of it happened. This recurs on every bonus, split, and (smaller) cash
dividend in 12 years of history.

## What's available (all scrapeable, most already ingested)

| Action | Source | Status |
|---|---|---|
| Cash dividend | `DividendArchive` → `fundamentals_dividends.cash_dividend_pct` | ingested (#57), has `record_date` |
| Stock dividend / bonus | `DividendArchive` → `fundamentals_dividends.stock_dividend_pct` | ingested (#57) — **the big one** |
| Rights issue | `/Home/RightArchive` (200 rows: Symbol, Right Offer ratio, Issue Price, Right Premium, Record Date, Year) | **not ingested** |
| Split (face-value change) | no dedicated source seen; DSE does these rarely, as a face-value change | treat as a bonus-equivalent factor when it appears |

So no new data source is needed for the common cases — the dividend archive
already carries what a bonus adjustment needs.

## Decision: adjust on read, not a stored `adjusted_close`

The spec (§8.2, §9.1) wants a stored `adjusted_close` column and a
`corporate_actions` table. **Recommend against**, for the same reasons #31 chose
on-read indicators over a precomputed table — and this is the consistent choice
with that decision, not a new departure.

1. **A stored adjusted series is never done.** Each new corporate action
   re-adjusts *every prior bar* of that symbol. So the column goes stale on every
   dividend and needs a full recompute.
2. **On the free tier a full recompute means truncate-and-reload of an 867k-row
   table** — no DML, no in-place update. That is exactly the #40 / #53 hazard, on
   the largest table in the dataset.
3. **On-read is cheap and always current.** An indicator reads ~365 bars for one
   symbol; a symbol has a handful of actions. Applying the factors at read time is
   trivial, and there is no staleness because there is nothing stored to go stale.
4. **The seam already exists.** `backend/price_series.from_price_history` (built in
   the 2026-07-17 architecture review) already turns raw rows into the
   oldest-first arrays indicators consume. The adjustment is one step there: apply
   the cumulative factor to closes/highs/lows before `compute_all`. One module,
   one place to be wrong — the same shape as `db.price_join`.

Raw stays raw in `price_archive` (already true). Adjusted is derived. `price_history`
can expose both a raw and an adjusted close so a chart can show either.

## The adjustment factor

For a bar on date `t`, multiply by the product of every action whose ex-date is
after `t`:

- **Stock dividend / bonus of `X%`:** factor = `1 / (1 + X/100)`. A 50% bonus →
  0.667; a 100% bonus → 0.5.
- **Face-value split `N:1`:** factor = `1/N`. Same shape.
- **Cash dividend:** see scope below — recommended **out** of v1 price adjustment.

Cumulative: a bar sees the product of all factors for actions after it, so older
bars are scaled down more, and the series becomes continuous across the ex-date.

## The ex-date convention — inferred from the data, confirm before shipping

lankabd gives **Record Date**, not ex-date, and the factor must apply to bars
*before* the ex-date. The EASTRNLUB data answers which:

```
record_date = 2025-12-22, and the price is still full (2501.5) on 2025-12-22,
dropping on 2025-12-23.
```

So **`record_date` is the last cum-dividend trading day**: adjust every bar with
`Date <= record_date` by the factor; leave `Date > record_date` alone. This was
read off one clean example and should be confirmed against two or three more
before the implementation ticket trusts it — an off-by-one here mis-scales exactly
one bar.

## v1 scope

- **Bonus / stock dividend: IN.** Biggest effect (the proven -31% case), data in
  hand.
- **Face-value split: IN** when one appears — identical factor shape.
- **Cash dividend: OUT of v1.** Adjusting a *price chart* for cash dividends is a
  total-return convention, not the default; TradingView/Yahoo "adjusted for
  splits" leave cash alone. A cash dividend also causes only a small gap, not a
  false crash, so it does not threaten indicator sanity. Keep it as a v2
  "total-return mode" option rather than baking it into the one adjusted series.
- **Rights: DEFER to v2.** `RightArchive` is not ingested, and the ex-rights
  adjustment needs the theoretical ex-rights price (subscription price + ratio),
  which is more than a single factor. Rare enough to defer.

## Interaction with the indicator pipeline (the reason #33 exists)

`price_series.from_price_history` is the single insertion point. It already exists,
is pure, and has 26 tests. The implementation ticket adds a factor lookup
(`symbol → [(ex-date-boundary, factor)]` from `fundamentals_dividends`) and applies
the cumulative factor there. `indicators.py` never learns adjustment exists.

## Also found — two data-quality landmines in `price_archive` (not #33, but they hit the same pipeline)

Both surfaced while validating the bonus jump, and both corrupt indicators today:

1. **Every row is duplicated** — each `(Symbol, Date)` appears twice in the query
   above. `price_series` does not dedupe, so every indicator double-counts every
   bar.
2. **A 0.0 close** (`EASTRNLUB 2026/06/30 close 0.0`). `price_series.to_number(0)`
   returns `0.0`, which is not None, so it is *kept* — a real -100% bar into every
   indicator, and a division near zero.

Filed separately — they belong with the scrapers / `price_series`, not corporate
actions.

## Follow-up tickets this implies

1. **Apply corporate-action adjustment in `price_series`** — bonus/split factor
   from `fundamentals_dividends`, applied to bars `<= record_date`. Confirm the
   ex-date convention against 2-3 more examples first. Blocks nothing; improves
   every indicator read.
2. **Ingest `RightArchive`** → a `corporate_actions`-style table, for the v2
   rights adjustment. Low priority.
3. **price_archive data quality: duplicate rows + zero closes** — dedupe on
   `(Symbol, Date)` and drop non-positive closes in `price_series`. Relates to #55
   (scraper tests) and the price archive scraper.

## Ex-date convention CONFIRMED against live data (#73, 2026-07-18)

The `record_date` = last-cum-day boundary was read off one example (EASTRNLUB).
#73 confirmed it against four more bonus events, all showing the price full
*through* `record_date` and dropping on the *next* trading day — so adjusting
bars with `Date <= record_date` is correct, **no off-by-one**:

| Symbol | Bonus | Factor 1/(1+X/100) | record_date close | ex-day (next) close | observed ratio |
|---|---|---|---|---|---|
| BRACBANK | 15% | 0.870 | 73.1 (2026/05/17) | 63.8 (2026/05/18) | 0.873 — near exact |
| UTTARABANK | 25% | 0.800 | 25.4 (2026/05/20) | 20.8 (2026/05/21) | 0.819 |
| PUBALIBANK | 20% | 0.833 | 38.7 (2026/05/20) | 33.2 (2026/05/21) | 0.858 |
| MTB | 12% | 0.893 | 13.9 (2026/06/18) | 12.9 (2026/06/21) | 0.928 (low price, noisy) |

Deviations from the theoretical factor are real ex-day price moves (bonus stocks
commonly bounce) plus rounding on low-priced shares — the direction and boundary
are unambiguous in every case. `backend/price_series.adjust_rows` and
`market_service._adjustment_actions` (#63) need no change.
