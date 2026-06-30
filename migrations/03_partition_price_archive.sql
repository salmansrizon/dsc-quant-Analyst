-- One-time migration: recreate lankabd_price_archive with clustering by Symbol.
-- Date is stored as STRING so date partitioning is skipped; clustering by Symbol
-- covers the primary query pattern: WHERE Symbol = @symbol.
-- BigQuery cannot change clustering spec in-place, so we copy through a temp table.
CREATE TABLE `dbt-test-420614.lankabd_dataset.lankabd_price_archive_tmp`
CLUSTER BY Symbol
AS SELECT * FROM `dbt-test-420614.lankabd_dataset.lankabd_price_archive`;

DROP TABLE `dbt-test-420614.lankabd_dataset.lankabd_price_archive`;

CREATE TABLE `dbt-test-420614.lankabd_dataset.lankabd_price_archive`
CLUSTER BY Symbol
AS SELECT * FROM `dbt-test-420614.lankabd_dataset.lankabd_price_archive_tmp`;

DROP TABLE `dbt-test-420614.lankabd_dataset.lankabd_price_archive_tmp`;
