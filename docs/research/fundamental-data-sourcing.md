# Fundamental-data sourcing — research findings (#32)

Date: 2026-07-17. Every claim was probed live against lankabd.com. Nothing here is inferred.

## The short answer

**lankabd.com exposes every fundamental the spec asks for, publicly, with no account.**
No manual/CSV entry. No missing data source. The original ticket assumed a gap that
does not exist.

The one thing standing between us and §5 was a CSRF header.

## Sources, in order of usefulness

### 1. `/api/company/*` — a JSON API. This is the answer.

The company page's RATIO / FINANCIAL STATEMENT / PEER COMPARISON tabs are React
widgets (`/Widget/COWidgetBundle.jsx`) that fetch JSON. A bare GET returns 400 with
an empty body — a *malformed request*, not a refusal. It wants a
`RequestVerificationToken` header, the same CSRF pattern `announcement.py` already
implements (scrape `__RequestVerificationToken` from the page, echo it back).

**With the token: 200.** No login. Verified against GP (`cid=160`).

#### `/api/company/FinancialRatiosV2?cid=N` — 19 KB, years 2023–2025

23 ratios per year across 5 categories (Asset Management & Asset Quality; Cash Flow
& Capital Adequacy; Efficiency & Productivity & Capital Strength; Liquidity &
Leverage; Profitability & Investment Return).

It carries the **entire spec §5 list**. GP 2025:

| Spec §5 field | API `Name` | Value |
|---|---|---|
| ROE | Return on Equity (ROE) | 0.527954 |
| ROA | Return on Assets (ROA) | 0.154589 |
| Debt/equity | Debt to Equity | 0.124953 |
| Current ratio | Current Ratio | 0.159223 |
| Net margin | Net Profit Margin | 0.187125 |
| Gross margin | Gross Profit Margin | 1.0 |
| EV/EBITDA-adjacent | EBITDA Margin | 0.311389 |

Each row also carries `Equation` and `BaseEquation` — the raw statement figures and
the formula. GP revenue is visible as `158057490000.0000 / …`. That is a free
audit trail: we can show *why* a ratio is what it is, not just assert it.

Note `Gross Profit Margin = 1.0` for GP — a telco with no COGS line. The API reports
what the statements say; garbage-in is possible and should not be smoothed over.

#### `/api/company/FinancialStatementCollection?cid=N&count=5` — 67 KB, 331 rows

Full statements, one row per line item per year:

```json
{"FSType": "Balance Sheet", "Year": 2021, "FSKey": "Property Plant & Equipment ",
 "FSOrder": 15, "FSValue": 60387950000.0, "FSCode": "BS96002", "IsVisible": true}
```

`FSType` ∈ Balance Sheet / Income Statement / Cash Flow. Revenue, assets,
liabilities, equity all present. `FSCode` is a stable machine key (`BS96002`) — the
same codes the ratio `BaseEquation`s reference, so ratios and statements join.

#### Other endpoints in the bundle (40 total)

```
StatsDividendHistory  FinancialSelectedPeerComparison  ShareholdingPattern
Owners  BoardMembers  Subsidiaries  DirectorBuySell  Profile  Auditors
StatsInterimFinReport  StatsRightIssue  PriceSensitiveInformation
TechnicalIndicator{MACD,MFI,Beta,VaR,StochasticOscillator,UltimateOscillator,14DayWilliamsPctR}
```

`FinancialSelectedPeerComparison` and `ShareholdingPattern` map directly onto spec
§5.5 (peer comparison) and §7.2. The `TechnicalIndicator*` set overlaps what we
already compute ourselves in `indicators.py` (#31) — ignore it; ours is tested.

**cid → symbol map is one request.** `/Home/DataMatrix` has 414 links of the form
`/Company/OverviewV2?cid=1&sn=Bank&cn=AB_Bank_PLC` with the ticker as link text.

### 2. `/Home/DividendArchive` — public HTML, no token, one request

**4,396 rows, 432 symbols, 2014–2026.** Symbol, Sector, Year, Dividend Type,
Cash Dividend %, RIU/Stock Dividend %, **EPS/EPU, NAV**, publish/record/AGM/year-end
dates.

GP: 27 rows of history. Latest — 2026, Interim, Cash Dividend 105%, EPS 10.52,
NAV 41.51.

**This beats the API on history: 12 years vs the API's 3.** Use both.

Caveat: `Dividend Type` is dirty free text. 3,409 "Annual", plus "Annuall",
"Semi- Annual", "Semi Annual", "Semi-annual", "Annual (11 Months)", and 754 blanks.
Normalise on ingest; keep the raw string.

### 3. `/Details/GetLatestEarnings` — public HTML, one request, live

410 rows, one per symbol: Publish Date, Symbol, Sector, Year, Annual/Quarter,
EPS/EPU, NAV. Real periodicity (Nine months 246, 1st Quarter 102, Annual 50,
Half Yearly 12). Latest publish date **2026-07-16 — yesterday**.

A snapshot, not history: scraped daily it *accretes* quarterly history. It does not
backfill.

### 4. Data we already have and do not use

`lankabd_price_archive` (867k rows) already carries per symbol per day:
`Market_Cap__BDT_bn_` (94% coverage), `Forward_PE` (60%), `Audited_PE` (63%),
`Beta` (patchy). `lankabd_datamatrix` carries `EPS` for all 414 symbols.

**The price archive's latest date is 2026/06/30 — 17 days stale**, because nothing
schedules the scrapers (#55).

## Terms of use

- **No `robots.txt`** (404). No crawl directives.
- **No anti-scraping, anti-automation, or rate-limit clause** in the Terms
  (`/Home/PrivacyStatement`). The "Legal Restrictions" section is about the
  jurisdictional legality of financial contracts, not access.
- The one relevant clause: *"This website contains material which is owned by or
  licensed to us. This material includes, but is not limited to, the design, look,
  appearance and graphics. Reproduction is prohibited other than in accordance with
  the copyright notice."*

That names **presentation**, not data, and DSE market data is public-record
financial information. **I am not a lawyer**, the document is boilerplate-vague, and
"not limited to" is doing real work in that sentence. The existing scrapers already
take this risk daily. If the portal ever monetises (spec §14 subscription tiers),
redistributing LankaBangla's data commercially is a materially different question
and deserves actual legal advice.

## Recommendation

**Do not split into tiers. The API gives everything; take it all.** My earlier
tier-split recommendation was written before the CSRF probe succeeded and is
withdrawn.

Three ingest paths, because the grains and cadences genuinely differ:

| Source | Requests | Cadence | Gives |
|---|---|---|---|
| `DividendArchive` | 1 | weekly | 12y EPS/NAV/dividends, all symbols |
| `GetLatestEarnings` | 1 | daily | current-quarter EPS/NAV, all symbols |
| `FinancialRatiosV2` + `FinancialStatementCollection` | 2 × 414 | quarterly | ratios + full statements, 3y |

The first two are one request each for every symbol — trivially cheap. The API path
is 828 requests, so it belongs on a quarterly cadence (statements only change when
a company reports) with the same `time.sleep(0.5)` politeness the existing scrapers
use. That is ~7 minutes.

### Schema

```sql
-- Grain: one row per symbol per reporting period. Append-only (#52).
fundamentals_reported (
  id STRING,              -- symbol|year|period
  symbol STRING, sector STRING,
  year INT64,
  period STRING,          -- normalised: ANNUAL | H1 | Q1 | Q2 | Q3 | 9M
  period_raw STRING,      -- what the site said, to audit the free-text mess
  eps FLOAT64, nav FLOAT64,
  cash_dividend_pct FLOAT64, stock_dividend_pct FLOAT64,
  publish_date DATE, record_date DATE, agm_date DATE, year_end_date DATE,
  source STRING,          -- dividend_archive | latest_earnings
  updated_at TIMESTAMP, is_deleted BOOL
)

-- Grain: one row per symbol per year per ratio. Long, not wide: the site has 23
-- ratios today and will have others tomorrow, and a wide table means a migration
-- every time. Long also stores the audit trail for free.
fundamentals_ratios (
  id STRING,              -- symbol|year|code
  symbol STRING, year INT64,
  code STRING,            -- RTAMAQ0210 — stable machine key
  name STRING,            -- "Total Asset Turnover"
  category STRING,
  result FLOAT64,
  equation STRING,        -- "158057490000.0000 / 191322941000.0000"
  updated_at TIMESTAMP, is_deleted BOOL
)

-- Grain: one row per symbol per year per statement line.
fundamentals_statements (
  id STRING,              -- symbol|year|fs_code
  symbol STRING, year INT64,
  fs_type STRING,         -- Balance Sheet | Income Statement | Cash Flow
  fs_code STRING,         -- BS96002 — joins to fundamentals_ratios.equation
  fs_key STRING,          -- "Property Plant & Equipment"
  fs_value FLOAT64,
  fs_order INT64,
  updated_at TIMESTAMP, is_deleted BOOL
)
```

**Ratios long, not wide.** The site exposes 23 today; a wide table means a schema
migration each time that changes, and we have just spent a ticket (#51) on exactly
that class of pain.

**Derived ratios (P/B, dividend yield, PEG) are computed on read in Python**, not
stored — mirroring the decision already made for technical indicators in #31. They
depend on a live price; storing them would need a second refresh path. ROE/ROA come
from the API directly, so no derivation needed.

**Dividend yield** = `(cash_dividend_pct × face_value) / price`. Face value is
**10 BDT** — user-confirmed 2026-07-17. Mutual funds may differ; worth a check when
the screener lands.

## Follow-up tickets this implies

1. **Ingest Tier 1** — DividendArchive + GetLatestEarnings → `fundamentals_reported`.
   One request each, no token. Unblocks EPS/NAV/dividend history immediately.
2. **Ingest the API** — cid map + FinancialRatiosV2 + FinancialStatementCollection →
   `fundamentals_ratios` / `fundamentals_statements`. Needs the CSRF dance
   `announcement.py` already has.
3. **Expose it** — `GET /api/market/fundamentals/{symbol}`, mirroring
   `/api/market/technical/{symbol}` from #31.
4. Scheduling belongs to **#55** (the ETL has no scheduler at all).

Unblocks **#36** (Stock Detail) and **#37** (Screener) — both blocked on this
ticket — and the peer-comparison and AI-scoring fog on #30.
