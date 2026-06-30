-- One-time migration: recreate lankabd_announcements with clustering by Symbol.
-- Date is stored as STRING so date partitioning is skipped; clustering by Symbol
-- covers the primary query pattern: WHERE Symbol = @symbol.
-- BigQuery cannot change clustering spec in-place, so we copy through a temp table.
CREATE TABLE `dbt-test-420614.lankabd_dataset.lankabd_announcements_tmp`
CLUSTER BY Symbol
AS SELECT * FROM `dbt-test-420614.lankabd_dataset.lankabd_announcements`;

DROP TABLE `dbt-test-420614.lankabd_dataset.lankabd_announcements`;

CREATE TABLE `dbt-test-420614.lankabd_dataset.lankabd_announcements`
CLUSTER BY Symbol
AS SELECT * FROM `dbt-test-420614.lankabd_dataset.lankabd_announcements_tmp`;

DROP TABLE `dbt-test-420614.lankabd_dataset.lankabd_announcements_tmp`;
