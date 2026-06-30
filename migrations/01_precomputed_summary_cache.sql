-- BigQuery Scheduled Query: refresh every 5 minutes
-- Target: lankabd_dataset.lankabd_market_summary_cache
--
-- Schedule this in BigQuery Console:
--   BigQuery > Scheduled Queries > Create > paste this SQL
--   Schedule: every 5 minutes
--   Destination table: lankabd_market_summary_cache
--   Write preference: WRITE_TRUNCATE

CREATE OR REPLACE TABLE `dbt-test-420614.lankabd_dataset.lankabd_market_summary_cache` AS
SELECT
    COUNT(*)                              AS total_stocks,
    COUNT(DISTINCT Sector)                AS total_sectors,
    ROUND(AVG(LTP), 2)                    AS avg_price,
    ROUND(SUM(Value_Turnover_), 2)        AS total_turnover,
    MAX(updated_at)                       AS last_updated
FROM `dbt-test-420614.lankabd_dataset.lankabd_datamatrix`;
