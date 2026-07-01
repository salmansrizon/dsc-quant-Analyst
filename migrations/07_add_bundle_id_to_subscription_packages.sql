-- One-time migration: add bundle_id to subscription_packages so a submitted
-- subscription can record which admin_bundles row (if any) it came from.
-- NULL means the subscription was custom-built (à la carte), not from a Package.
-- Explicit ALTER TABLE, not relying on _insert_rows' dataframe-autodetect
-- (ALLOW_FIELD_ADDITION) — that's what produced the existing schema-inference
-- bugs on this table (medium as STRING instead of REPEATED, timestamp columns
-- inferred as INTEGER); a column whose first-ever insert is NULL is
-- especially likely to get inferred wrong.
ALTER TABLE `dbt-test-420614.lankabd_dataset.subscription_packages`
ADD COLUMN IF NOT EXISTS bundle_id STRING;
