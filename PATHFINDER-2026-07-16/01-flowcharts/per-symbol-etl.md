# Flowchart — Per-symbol incremental ETL

`priceArchive.py` + `announcement.py`. One skeleton, two payloads. No in-repo callers; both are
`python <script>.py` only. No scheduler, cron, or CI invocation exists.

```mermaid
flowchart TD
  A["__main__<br/>priceArchive.py:380"] --> B["scrape_all_symbols_price_data<br/>priceArchive.py:192"]
  A2["__main__<br/>announcement.py:428"] --> B2["scrape_all_symbols_announcements<br/>announcement.py:203"]

  B --> C["BigQueryHelper()<br/>priceArchive.py:194"]
  B2 --> C2["BigQueryHelper()<br/>announcement.py:205"]
  C --> D["_ensure_dataset (may CREATE)<br/>bigquery_helper.py:32"]
  C2 --> D

  B --> E["to_date = get_date_range(3)<br/>priceArchive.py:198"]
  B2 --> E2["GLOBAL get_last_date('Date')<br/>announcement.py:207"]
  E2 --> F2["fromdate = last+1d, else 3y<br/>announcement.py:212-223"]

  E --> G["get_symbols_from_sectors<br/>priceArchive.py:53"]
  F2 --> G2["get_symbols_from_sectors<br/>announcement.py:50"]
  G --> H["SELECT DISTINCT Symbol FROM lankabd_datamatrix<br/>priceArchive.py:58"]
  G2 --> H
  H -->|"[] on error"| X["return None (abort)<br/>priceArchive.py:203 / announcement.py:231"]

  H --> L["for idx, symbol in symbols<br/>priceArchive.py:211"]
  H --> L2["for idx, symbol in symbols<br/>announcement.py:240"]

  L --> M["PER-SYMBOL get_last_date(Symbol=sym)<br/>priceArchive.py:219"]
  M --> N["symbol_from_date = last+1d, else 3y<br/>priceArchive.py:222-229"]
  N --> O["scrape_price_archive<br/>priceArchive.py:68"]
  O --> P["GET lankabd.com (cookies)<br/>priceArchive.py:84"]
  P --> Q["GET /Home/PriceArchive<br/>priceArchive.py:96"]
  Q --> R["BeautifulSoup parse table<br/>priceArchive.py:101-147"]
  R --> S["rename cols + null indicators<br/>priceArchive.py:150-178"]
  S --> T["to_numeric coerce<br/>priceArchive.py:237-242"]
  T --> U["all_data.append<br/>priceArchive.py:246"]
  O -->|"except -> None"| V["failed_symbols.append<br/>priceArchive.py:250"]
  U --> W["time.sleep(0.5)<br/>priceArchive.py:253"]
  V --> W
  W --> L

  L2 --> O2["scrape_announcement<br/>announcement.py:65"]
  O2 --> P2["GET /MarketAnnouncements?catName=Archive<br/>announcement.py:76"]
  P2 --> Q2["extract __RequestVerificationToken<br/>announcement.py:79"]
  Q2 --> R2["POST /MarketAnnouncements<br/>announcement.py:101"]
  R2 --> S2["parse div.list-group-item<br/>announcement.py:107-143"]
  S2 -->|"no items"| S3["FALLBACK table parse<br/>announcement.py:151-188"]
  S2 --> T2["filter to allowed_columns<br/>announcement.py:265-266"]
  S3 --> T2
  T2 --> U2["all_data.append<br/>announcement.py:269"]
  O2 -->|"except -> None"| V2["failed_symbols.append<br/>announcement.py:272"]
  L2 -->|"fetch_all_pages"| PG["while page loop + sleep(0.3)<br/>announcement.py:245-255"]
  PG --> O2
  U2 --> W2["time.sleep(0.5)<br/>announcement.py:292"]
  V2 --> W2
  W2 --> L2

  L -->|"loop done"| Y["pd.concat<br/>priceArchive.py:257"]
  L2 -->|"loop done"| Y2["pd.concat + normalize Date<br/>announcement.py:295-299"]

  Y --> Z["upload_dataframe('lankabd_price_archive')<br/>priceArchive.py:261"]
  Y2 --> Z2["upload_dataframe('lankabd_announcements')<br/>announcement.py:303"]
  Z --> ZZ["load_table_from_dataframe WRITE_APPEND<br/>bigquery_helper.py:90"]
  Z2 --> ZZ
  ZZ --> TERM["ROWS LANDED IN BIGQUERY"]
  Z -->|"except: log only"| CSV["to_csv still runs<br/>priceArchive.py:268"]
  Z2 -->|"except: log only"| CSV2["to_csv still runs<br/>announcement.py:309"]
  CSV --> RET["return combined_df<br/>priceArchive.py:280"]
  CSV2 --> RET2["return combined_df<br/>announcement.py:317"]

  V3["by_symbol / by_sector variants<br/>priceArchive.py:286,308 / announcement.py:323,342"] --> V4["CSV ONLY — no BigQuery upload"]
```

## Notable behaviours (evidence)

- **Incremental logic diverges materially.** `priceArchive.py:219` calls `get_last_date` **per symbol inside
  the loop** (N queries for N symbols). `announcement.py:207` calls it **once, globally, before the loop** —
  one `fromdate` for every symbol.
- **Upload failure exits 0.** Both catch upload errors and only log (`priceArchive.py:263`,
  `announcement.py:305`); the CSV still writes and the function still returns the DataFrame. A failed ETL
  looks like a successful one to any caller or scheduler.
- **No dedupe.** `get_last_date` + 1 day is the only overlap defense on an append-only table.
- **Error isolation differs.** priceArchive catches bare `Exception`; announcement catches only
  `(AttributeError, ValueError, KeyError)` — a `TypeError` in parsing aborts the whole run.
- **by_symbol/by_sector variants never upload** (`:286`, `:308`, `:323`, `:342`) — CSV only. Only the
  `__main__` all-symbols paths land rows.
- Latent: `priceArchive.py:228`'s `except` handler formats `last_date`, bound only inside the `try` at `:219`.
  Not currently reachable (`get_last_date` swallows its own exceptions), but a live `UnboundLocalError` if
  that ever changes.

## External dependencies

- **Reads:** `lankabd_datamatrix` (produced by dataGrid) — data-coupled, not an import edge.
- **Calls:** `utils/bigquery_helper.BigQueryHelper` → `backend/db.py`; `utils/logger.Log`.
- **Writes:** `lankabd_price_archive`, `lankabd_announcements` (append-only), CSV to cwd, `logs/`.

## Confidence

High on control flow and side effects (both files read in full). Gaps: live lankabd.com HTML not verified,
so which parse branch fires is inferred from code order; no test coverage exists for either script.
