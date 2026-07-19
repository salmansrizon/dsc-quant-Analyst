# Handoff Prompts — backend/ (2026-07-16)

Copy any block into `/make-plan`. Ordered by severity. U1 and U2 are correctness; U3/U4 are consolidation;
U5 needs a live credential before it can be planned properly.

---

## U1 — Fix and migrate alert_checker

```
/make-plan Rewrite backend/alert_checker.py (66 lines) onto the post-#44 data-access idiom, fixing three defects.

FIRST verify against live BigQuery whether the price_alerts column is `symbol` or `Symbol` — the whole plan branches on it. alerts_service.py:31 writes `symbol` and get_alerts reads `a.symbol`, but alert_checker.py:26 merges on='Symbol' and :46 reads row['Symbol']. If the live column is lowercase, check_alerts raises KeyError before any alert fires and the batch job has never worked.

Defects to fix:
1. The symbol/Symbol merge key mismatch (alert_checker.py:26,46).
2. alert_checker.py:51-55 interpolates alert ids and a timestamp directly into an UPDATE string. It is the only mutation in the backend bypassing db.execute_dml. Replace with a new alerts_service.mark_triggered(alert_ids) using db.execute_dml with a bigquery.ArrayQueryParameter and a typed TIMESTAMP param.
3. alert_checker.py:60 is a comment-only notification TODO placed AFTER the is_triggered=true commit at :57 — the alert is marked consumed and the user is never told. Do not build the notification channel (that is issue #34, still unspecified). Do reorder so the commit cannot precede a send that does not exist yet, and say plainly in the plan what remains lost.

Also: alert_checker.py:4 imports BigQueryHelper — after this it should reach BigQuery only via alerts_service/db. Returns are inconsistent (None at :18, list at :61, [] at :63) — normalize.

Cite PATHFINDER-2026-07-16/01-flowcharts/sector-etl-and-alert-triggering.md.

Anti-patterns: do not build a notification abstraction; do not add an outbox table without the #34 decision; do not keep the BigQueryHelper path "for the batch job".
```

## U2 — Completeness gate before dataGrid's truncate

```
/make-plan Add a completeness gate to backend/dataGrid.py:181 scrape_all_sectors before it truncates lankabd_datamatrix.

Today the only guard on a WRITE_TRUNCATE (dataGrid.py:215 -> bigquery_helper.py:82) is `if all_data:` at dataGrid.py:204, which passes when ONE of N sectors succeeded. scrape_lankabd swallows per-sector failures and returns None (:174-179); scrape_all_sectors logs a warning and continues (:198-199). So a half-failed run replaces the entire symbol universe with a partial one.

Blast radius: priceArchive.py:57 and announcement.py:54 both SELECT DISTINCT Symbol FROM lankabd_datamatrix, so they silently narrow to the survivors; alerts_service.py:19 LEFT JOINs it, so missing symbols return current_price = NULL. No staging table exists — the truncate is unrecoverable except by a successful rerun.

This is the same class of bug as issue #40 (truncate-and-reload destroying rows the run never saw), one layer up. Read #40 first.

Required behavior: refuse to truncate unless every sector from get_available_sectors() (dataGrid.py:42) returned data. On a partial scrape: write the CSV, log which sectors failed, exit non-zero, leave the table untouched. A stale-but-complete universe beats a fresh-but-partial one.

Cite PATHFINDER-2026-07-16/01-flowcharts/sector-etl-and-alert-triggering.md.

Anti-patterns: no partial-write mode behind a flag; no staging-table machinery unless the plan shows the gate alone is insufficient; do not silently swallow the non-zero exit.
```

## U3 — db.query_rows()

```
/make-plan Add db.query_rows(sql, params) to backend/db.py and route all 9 read call sites through it.

#41/#43 gave the write path db.insert_rows and db.execute_dml but left reads unabstracted. The idiom
`[dict(r) for r in bq.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params)).result()]`
is copied verbatim at 9 sites: alerts_service.py:24, portfolio_service.py:35, watchlist_service.py:23, market_service.py:24,74,82,98,168, user_service.py:129.

Target signature:
    def query_rows(sql: str, params: list | None = None) -> list[dict]

Each call site becomes `return db.query_rows(sql, params)`. Then delete the module-level `bq = db.client()` preamble from market_service.py:7-8, watchlist_service.py:9-10, alerts_service.py:9-10, portfolio_service.py:9-10, user_service.py:13-14.

That preamble deletion is the real prize: it closes the eager import-time client follow-up already recorded on #43. Reads become stubbable via db._client exactly as mutations already are — backend/tests/test_bq_mutations.py shows the pattern to extend. Add read-path tests that were previously impossible.

Cite PATHFINDER-2026-07-16/02-duplication-report.md section D4.

Anti-patterns: not a query builder, not a repository class, not an ORM, no fluent chaining. One function. The SQL stays written out at each call site where it is readable.
```

## U4 — backend/scrapers/common.py

```
/make-plan Extract the triplicated scraper preamble into backend/scrapers/common.py.

Verified byte-identical duplication (diff, not eyeballing):
- HEADERS dict, 9 lines, byte-identical x3: announcement.py:19-27, priceArchive.py:21-29, dataGrid.py:19-27.
- get_session, 11 lines, identical modulo one docstring x3: announcement.py:30-40, priceArchive.py:32-43, dataGrid.py:29-39. Retry policy (total=3, backoff_factor=1, status_forcelist=[429,500,502,503,504]) triplicated.
- get_symbols_from_sectors, 15 lines, byte-identical x2: announcement.py:50-64 == priceArchive.py:53-67.
- get_date_range, 5 lines x2: announcement.py:43-47 vs priceArchive.py:46-50, differs only by docstring and a local name.
- The sector->symbol block, ~17 lines x2: announcement.py:346-362 vs priceArchive.py:315-331, whitespace-only divergence. Both interpolate `sector` into SQL — collapse to ONE get_symbol_universe(sector=None) passing sector as a query parameter.

Total: ~35 lines with a 0-line semantic delta.

Import note: these scripts run as `python priceArchive.py` with cwd=backend, NOT as a package. backend/utils/bigquery_helper.py already solves this exact problem — read its try/except ImportError block and its subprocess test at backend/tests/test_bigquery_helper.py before choosing an approach.

Cite PATHFINDER-2026-07-16/02-duplication-report.md sections D1/D2.

Anti-patterns: NO BaseScraper class. The three scrapers have genuinely different shapes — dataGrid has no symbol fanout, announcement paginates and POSTs a CSRF token, priceArchive GETs. Inheritance would force those into template-method hooks and turn three readable scripts into one unreadable hierarchy. A module of plain functions, imported. Do NOT consolidate the scrape_all_* orchestration loops (D3) — that is where the legitimate specialization lives.
```

## U5 — Reconcile export table names (needs a live credential first)

```
/make-plan Reconcile backend/exports.py table names against live BigQuery.

exports.py:31 queries db.table_id('announcements') and exports.py:57 db.table_id('price_archive') — unprefixed. Every other reader and writer in the repo uses the lankabd_ prefix: market_service.py:92,163, announcement.py:303, priceArchive.py:261, upload_csvs.py:35,38. exports.py:78 itself uses lankabd_datamatrix. So two of the three admin exports likely hit a missing table.

Confirmed pre-existing, NOT introduced by the #41 migration — `git show db929ca~1:backend/exports.py` has the same unprefixed names hardcoded.

DO NOT just edit the strings. First list the actual tables in the dataset. If legacy `announcements`/`price_archive` tables exist and hold data, the fix is a backfill or rename decision, not a string change — surface that to the user rather than picking.

Note test_admin_exports.py cannot catch this: its fixtures error at setup on a real-BigQuery signup (part of the 1-failed/7-error pre-existing suite state). Any fix needs a test that would actually fail on the wrong name.

Cite PATHFINDER-2026-07-16/02-duplication-report.md section D6.

Anti-patterns: do not add a table-existence fallback that silently tries both names.
```
