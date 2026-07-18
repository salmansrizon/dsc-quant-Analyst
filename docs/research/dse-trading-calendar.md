# DSE trading-calendar / holidays source — research findings (#67)

Date: 2026-07-18. For #34's Phase-3 "market open/close" and "summary" digest
alerts, which need to know when the DSE is actually trading.

## The shape of the problem

"Is the DSE trading right now?" splits into two parts with very different
volatility:

1. **Weekly schedule + hours — stable, hardcode it.** The DSE trades
   **Sunday–Thursday**, **10:00–14:30 Asia/Dhaka (BST = UTC+6)**: a continuous
   session 10:00–14:20, then a post-close 14:20–14:30. Ramadan shortens it to
   10:00–14:00. Friday–Saturday closed. This has been stable for years and is a
   constant, not a feed. (It matches the 09:30-UTC ETL cron in #55/#69, ~1h
   after the 08:30-UTC close.)

2. **Public holidays — irregular, must be data.** ~23–25 market holidays a
   year, and the big ones (Eid-ul-Fitr, Eid-ul-Adha, Shab-e-Barat, Muharram,
   Mawlid) are **lunar and shift every year** — their dates aren't knowable by
   formula and are announced by the exchange, sometimes adjusted at short notice
   for moon sighting. 2026 has two multi-day closures (Eid-ul-Fitr Mar 19–23,
   Eid-ul-Adha May 26–30). So the holiday list cannot be hardcoded once; it is a
   yearly-refreshed dataset.

## Sources found

| Source | What it gives | Usable? |
|---|---|---|
| **dsebd.org/hts.php** ("Holidays and Trading Sessions") | The authoritative list — trading sessions + the year's holidays, from the exchange itself | **Yes, but** the site's TLS certificate chain doesn't verify (`unable to verify the first certificate`). A scraper needs `verify=False` (or a pinned CA). This is the same site class we already scrape; announcement.py already talks to lankabd. |
| **calendarlabs.com/dse-market-holidays-YYYY** | A clean structured HTML table (Day / Date / Holiday / Comments), one page per year, links for 2025–2028 | **Yes** — easiest to parse, and multi-year, but third-party (a mirror of the official list, so trust it less than dsebd.org). Good as a cross-check. |
| **tradinghours.com / markethours.io** | Hours + holidays via a commercial API | Paid; overkill for one alert type. |

## Recommendation

- **Hardcode the weekly schedule + session hours** (Sun–Thu, 10:00–14:30 Dhaka,
  Ramadan variant) as constants. It doesn't change.
- **Maintain a small holidays dataset, refreshed yearly**, not a live per-check
  scrape. ~25 rows/year. Two viable ways to fill it, in order of preference:
  1. A **committed config** (`dse_holidays.json` keyed by year) curated from the
     annual DSE holiday circular / dsebd.org/hts.php. Simplest, no runtime
     dependency, and a human eyeballs the moon-dependent dates once a year. A
     year's worth is trivial to enter.
  2. If automation is wanted later, a **once-a-year scrape of dsebd.org/hts.php**
     (with `verify=False`), parsed via the shared `scrapers/common.header_keyed_rows`
     (#60) — the holiday list is an HTML table. calendarlabs as a cross-check.
- **"Is trading now"** = weekday ∈ {Sun–Thu} **and** time ∈ session **and** date
  ∉ holidays. Ramadan window is a refinement, not needed for v1 open/close.

## Scope / priority

Confirmed low priority: this unblocks exactly **one** of ten alert types
(market open/close), and only in Phase 3. The weekly-hours constant alone is
enough to ship a crude open/close signal that is wrong only on the ~25 holidays
a year; the holidays dataset upgrades it to correct. No blocker to Phases 1–2.

## Sources

- https://www.dsebd.org/hts.php — official DSE Holidays & Trading Sessions
- https://www.calendarlabs.com/dse-market-holidays-2026/ — structured 2026 list
- https://www.tradinghours.com/markets/dse — hours + holiday summary
