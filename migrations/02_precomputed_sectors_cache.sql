-- BigQuery Scheduled Query: refresh every 5 minutes
-- Target: lankabd_dataset.lankabd_sectors_cache
--
-- Schedule this in BigQuery Console:
--   BigQuery > Scheduled Queries > Create > paste this SQL
--   Schedule: every 5 minutes
--   Destination table: lankabd_sectors_cache
--   Write preference: WRITE_TRUNCATE

CREATE OR REPLACE TABLE `dbt-test-420614.lankabd_dataset.lankabd_sectors_cache` AS
SELECT
    Sector,
    COUNT(*)                              AS stock_count,
    ROUND(AVG(LTP), 2)                    AS avg_ltp,
    ROUND(AVG(__Change), 2)               AS avg_change,
    SUM(Volume_Qty_)                      AS total_volume,
    ROUND(SUM(Value_Turnover_), 2)        AS total_turnover
FROM `dbt-test-420614.lankabd_dataset.lankabd_datamatrix`
WHERE Sector IS NOT NULL AND Sector != ''
GROUP BY Sector
ORDER BY Sector;
