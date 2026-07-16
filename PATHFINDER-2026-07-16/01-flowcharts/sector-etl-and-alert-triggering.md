# Flowcharts — Sector snapshot ETL + Alert triggering

## Feature A — Sector snapshot ETL (`dataGrid.py`)

```mermaid
flowchart TD
  A["__main__<br/>dataGrid.py:227"] --> B["scrape_all_sectors<br/>dataGrid.py:181"]
  B --> C["get_available_sectors<br/>dataGrid.py:42"]
  C --> C1["HTTP GET lankabd.com/ + /Home/DataMatrix<br/>dataGrid.py:50-51"]
  C1 --> C2["parse select#sectorddl<br/>dataGrid.py:54-64"]
  C2 --> D{"sectors empty?<br/>dataGrid.py:185"}
  D -- yes --> D1["log error, return None<br/>dataGrid.py:186-187"]
  D -- no --> E["for sector in sectors<br/>dataGrid.py:191"]
  E --> F["scrape_lankabd(sector)<br/>dataGrid.py:72"]
  F --> F2{"table#TableDataMatrix?<br/>dataGrid.py:113-117"}
  F2 -- no --> F3["warn, return None<br/>dataGrid.py:116-117"]
  F2 -- yes --> F4["DataFrame + clean + numeric coerce<br/>dataGrid.py:131-153"]
  F4 --> F5["filter allowed_columns + Sector<br/>dataGrid.py:156-167"]
  F5 --> G["append to all_data<br/>dataGrid.py:196"]
  F3 --> G2["warn 'No data for sector'<br/>dataGrid.py:199"]
  G2 --> H
  G --> H["sleep(1)<br/>dataGrid.py:201"]
  H --> E
  E -- done --> I{"all_data non-empty?<br/>dataGrid.py:204"}
  I -- no --> I1["warn, return None (no BQ write)<br/>dataGrid.py:223-224"]
  I -- yes --> J["pd.concat<br/>dataGrid.py:205"]
  J --> K["write CSV<br/>dataGrid.py:208-209"]
  K --> L["BigQueryHelper()<br/>dataGrid.py:214"]
  L --> M["upload_dataframe(truncate=True)<br/>dataGrid.py:215"]
  M --> N["load_table_from_dataframe WRITE_TRUNCATE<br/>bigquery_helper.py:82-91"]
  N -- ok --> O["return combined_df<br/>dataGrid.py:221"]
  N -- exc --> P["log + raise<br/>dataGrid.py:217-219"]
```

### Truncate semantics — the destructive path

`scrape_lankabd` swallows every per-sector failure and returns `None` (`:174-179`); `scrape_all_sectors`
only logs a warning and continues (`:198-199`). There is **no completeness gate** — the only guard is
`if all_data:` (`:204`), which passes when **one** sector succeeded. A half-failed run therefore concatenates
the partial set and issues `WRITE_TRUNCATE` (`bigquery_helper.py:82-83`), **replacing the entire symbol
universe with the partial one.**

Downstream blast radius: `priceArchive.get_symbols_from_sectors` (`priceArchive.py:57`) and
`announcement.py:54` do `SELECT DISTINCT Symbol FROM lankabd_datamatrix`, so they silently scrape only the
surviving subset. `alerts_service.get_alerts` (`alerts_service.py:19`) LEFT JOINs it, so missing symbols
yield `current_price = NULL`. No snapshot or staging table exists — the truncate is unrecoverable except by
a successful rerun.

## Feature B — Alert triggering (`alert_checker.py`)

```mermaid
flowchart TD
  A["__main__<br/>alert_checker.py:65"] --> B["check_alerts<br/>alert_checker.py:8"]
  B --> C["BigQueryHelper()<br/>alert_checker.py:9"]
  C --> D["SELECT * FROM price_alerts WHERE is_triggered=false<br/>alert_checker.py:12-14"]
  D --> E{"alerts.empty?<br/>alert_checker.py:16"}
  E -- yes --> E1["print, return None<br/>alert_checker.py:17-18"]
  E -- no --> F["SELECT Symbol, LTP FROM lankabd_datamatrix<br/>alert_checker.py:21-23"]
  F --> G["merge(on='Symbol', how='left')<br/>alert_checker.py:26"]
  G --> H["to_numeric LTP<br/>alert_checker.py:27"]
  H --> I["iterrows<br/>alert_checker.py:31"]
  I --> J{"LTP NaN?<br/>alert_checker.py:32-33"}
  J -- yes --> I
  J -- no --> K{"direction above/below vs target<br/>alert_checker.py:39-42"}
  K -- no --> I
  K -- yes --> L["triggered_ids.append + print<br/>alert_checker.py:44-46"]
  L --> I
  I -- done --> M{"triggered_ids?<br/>alert_checker.py:49"}
  M -- no --> M1["return []<br/>alert_checker.py:63"]
  M -- yes --> N["build f-string UPDATE, ids inlined<br/>alert_checker.py:50-56"]
  N --> O["bq.client.query(sql_update).result()<br/>alert_checker.py:57"]
  O --> P["TODO notification stub<br/>alert_checker.py:60"]
  P --> Q["return triggered_ids<br/>alert_checker.py:61"]
```

### Findings

- **Column-case mismatch (suspected hard failure).** `create_alert` writes the column `symbol`
  (`alerts_service.py:31`) and `get_alerts` reads `a.symbol` (`:15`). But `alert_checker.py:26` merges
  `on='Symbol'` and `:46` reads `row['Symbol']`. With `SELECT *`, the alerts frame carries `symbol`, so the
  merge key is absent on the left → `KeyError: 'Symbol'` before any update. This precedes every other issue
  in this feature.
- **Unparameterized DML.** `:51-55` interpolates `id` values and `now` straight into the SQL. Every other
  mutation uses `db.execute_dml` with `ScalarQueryParameter` (`db.py:119-128`, `alerts_service.py:44-49`).
  Ids are server-generated `uuid4` (`alerts_service.py:28`), so it is not exploitable today — it is a
  defense-in-depth gap, not a live vulnerability.
- **Notification is committed-then-dropped.** `:60` is a comment-only TODO placed *after* `is_triggered=true`
  is committed at `:57`. The alert is marked consumed and the user is never told. Lossy by construction: no
  outbox, no retry state.
- Not double-triggerable (`WHERE is_triggered = false` + the UPDATE make it once-only).
- Inconsistent returns: `None` (`:18`), `triggered_ids` (`:61`), `[]` (`:63`).

## External dependencies

`requests`/Retry, beautifulsoup4/lxml, pandas, numpy, google-cloud-bigquery; `utils.logger.Log`;
`utils.bigquery_helper.BigQueryHelper` → `backend/db.py`. Network: `lankabd.com`. BigQuery:
`lankabd_datamatrix` (A writes/truncates; B, priceArchive, announcement, alerts_service read),
`price_alerts` (B reads + updates).

## Confidence

High on control flow (both files read in full, plus every downstream `lankabd_datamatrix` reader).
**Gap:** no DDL for `price_alerts` exists in the repo, so the `symbol` vs `Symbol` mismatch is inferred from
the writer/reader in `alerts_service.py` rather than confirmed against the live table. If the deployed table
has a legacy capitalized column, that finding drops.
