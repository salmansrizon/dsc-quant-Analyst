-- One-time migration: create admin_bundles with an explicit schema.
-- Deliberately not relying on load_table_from_dataframe's autodetect-create —
-- that's what produced subscription_packages' schema bug (medium as STRING
-- instead of REPEATED, timestamp columns inferred as INTEGER).
CREATE TABLE `dbt-test-420614.lankabd_dataset.admin_bundles` (
  id STRING NOT NULL,
  name STRING NOT NULL,
  medium ARRAY<STRING>,
  alert_channel BOOL NOT NULL,
  digest_channel BOOL NOT NULL,
  alert_cap INT64 NOT NULL,
  digest_cadence STRING NOT NULL,
  price FLOAT64 NOT NULL,
  is_active BOOL NOT NULL,
  created_at TIMESTAMP NOT NULL,
  created_by STRING NOT NULL
);
