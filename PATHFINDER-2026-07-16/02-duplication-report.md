# Duplication Report — backend/ (2026-07-16)

All claims cite ≥2 `file:line` locations and were verified with `diff` on extracted line ranges, not by eye.

## Resolved since 2026-07-15

The prior audit's headline finding — **four independent BigQuery client bootstraps** — is gone. `bq_service.py`
is deleted; `db.py` is the single access point; the four `*_service.py` modules all do `from . import db`;
`BigQueryHelper` is a shim over `db.client()`. Not re-reported below.

---

## D1 — Scraper preamble skeleton: ~35 identical lines × 3 files

- **HEADERS dict, 9 lines, byte-identical ×3**: `announcement.py:19-27`, `priceArchive.py:21-29`,
  `dataGrid.py:19-27`. Zero diff.
- **`get_session`, 11 lines, identical modulo one docstring/comment ×3**: `announcement.py:30-40`,
  `priceArchive.py:32-43`, `dataGrid.py:29-39`. The retry policy
  (`total=3, backoff_factor=1, status_forcelist=[429,500,502,503,504]`) is triplicated.
- **`get_symbols_from_sectors`, 15 lines, byte-identical ×2**: `announcement.py:50-64` ≡
  `priceArchive.py:53-67`. Zero diff.
- **`get_date_range`, 5 lines ×2**: `announcement.py:43-47` vs `priceArchive.py:46-50` — differs only by
  docstring and a local name (`past_date`/`start_date`).

**Why diverged:** copy-paste seeding of each scraper; all drift is comment-only.
**Verdict: accidental.** ~35 duplicated lines with a **0-line semantic delta**. No specialization exists.

## D2 — Sector→symbol query block: ~17 lines duplicated

`announcement.py:346-362` vs `priceArchive.py:315-331`. Same `SELECT DISTINCT Symbol` + conditional
`WHERE Sector = '{sector}'` build, same try/except, same two-branch logging. Divergence: whitespace only.
**Verdict: accidental.** Note both copies interpolate `sector` directly into SQL.

## D3 — `scrape_all_*` orchestration shape: ~90 lines, 4 copies

`announcement.py:203-322`, `announcement.py:342-428`, `priceArchive.py:192-285`, `priceArchive.py:308-381`;
partially `dataGrid.py:181-227`. Shared skeleton: `all_data`/`success_count`/`failed_symbols` accumulators →
`for idx, symbol in enumerate(symbols, 1)` → `time.sleep(0.5)` → `pd.concat(ignore_index=True)` →
`bq.upload_dataframe` in try/except → `to_csv` → `"\n" + "="*60` banner → `failed_symbols[:10]` truncated
warning (that last line is byte-identical at `announcement.py:317` and `priceArchive.py:279`). The
`fetch_all_pages` pagination loop is duplicated **within** `announcement.py` (241-256 vs 380-395, ~14 lines).

**Verdict: mostly accidental.** Legitimate specialization is narrow and real: announcement does per-table
incremental `get_last_date`, priceArchive does per-symbol (`priceArchive.py:214-227`); column cleanup differs
(allowed-column filter vs numeric coercion). The ~90-line figure is structural correspondence, not
byte-identity — the consolidatable subset is smaller.

## D4 — `db.py` deepened writes but left reads unabstracted

Preamble repeated verbatim in 5 modules: `market_service.py:7-8`, `watchlist_service.py:9-10`,
`alerts_service.py:9-10`, `portfolio_service.py:9-10`, `user_service.py:13-14`.

The terminal idiom
`return [dict(r) for r in bq.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params)).result()]`
appears **9×**: `alerts_service.py:24`, `portfolio_service.py:35`, `watchlist_service.py:23`,
`market_service.py:24,74,82,98,168`, `user_service.py:129`.

`get_watchlist` (13-23), `get_alerts` (13-24) and `get_portfolio` (22-35) are the same 4-step template
(SQL with `LEFT JOIN lankabd_datamatrix ... ON x.symbol = d.Symbol`, single `uid` param, dict-map).

**Verdict: accidental.** The SQL bodies are legitimately distinct; the wrapper is not. #41/#43 gave writes
`insert_rows`/`execute_dml` but gave reads nothing — **that asymmetry is the duplication.** It is also why the
read path is not stubbable in tests (the follow-up already noted on #43).

## D5 — Two competing data-access idioms still coexist

Post-#43 idiom (`db.table_id`, backtick-quoted, `db.execute_dml`) is used by the services and exports. The
legacy idiom (`BigQueryHelper()` + `bq._get_full_table_id(...)` + manual backticks + `bq.client.query(...)`)
survives at `announcement.py:52-56,348`, `priceArchive.py:55-59,317`, `dataGrid.py:215`,
`alert_checker.py:11-23`.

`alert_checker.py:49-53` additionally builds an `UPDATE` by interpolating `ids_str` and `now` — the **only**
mutation in the backend not routed through `db.execute_dml`.

**Verdict: accidental** — an unfinished migration, not specialization. #44 made `BigQueryHelper` a shim, which
unified the *client*; it did not unify the *idiom*.

## D6 — Table-name literal divergence (suspected live bug)

`lankabd_datamatrix` is hardcoded at 13+ sites (`market_service.py:19,44,58,70,78,178`,
`watchlist_service.py:18`, `alerts_service.py:19`, `portfolio_service.py:30,108`, `announcement.py:54,348`,
`priceArchive.py:57,317`, `alert_checker.py:21`, `exports.py:78`).

More seriously: `exports.py:31` queries `db.table_id('announcements')` and `exports.py:57`
`db.table_id('price_archive')` — **unprefixed** — while every other reader and writer uses the `lankabd_`
prefix (`market_service.py:92,163`, `announcement.py:303`, `priceArchive.py:261`, `upload_csvs.py:35,38`).

**Verdict: accidental divergence.** The unprefixed names appear nowhere else in the repo, so two of the three
admin exports likely hit a missing table. **Confirmed pre-existing** — `git show db929ca~1:backend/exports.py`
has the same unprefixed names hardcoded, so #41 did not introduce this. Not proven against live BigQuery;
`test_admin_exports.py` cannot catch it because its fixtures error out at setup on a real-BigQuery signup.

---

## Confidence + gaps

High on D1/D2/D6 (`diff`-verified byte-level, grep-enumerated). High on D4/D5 (grep-exhaustive). Medium on
D3 line counts (structural, not byte-identity). **Gaps:** `indicators.py` (392 lines), `api.py` route bodies,
and the HTML-parsing internals of the three `scrape_*` functions were not read — a fourth, parse-level
duplication may exist there.
