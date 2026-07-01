-- One-time migration: create pricing_weights and seed placeholder values.
-- bq_service.get_pricing() and the Settings.jsx estimator have referenced this
-- table since the custom-builder UI was built, but it never existed in
-- production, so GET /api/subscriptions/pricing has been silently failing.
-- Schema/lookup shape (dimension, key, weight_price) matches how
-- Settings.jsx looks weights up: medium rows are matched on
-- (dimension='medium', key=<medium>); alert/digest rows are matched on
-- key='alert' / key='digest' alone.
-- Seed values are placeholders — there's no admin UI for editing weights in
-- this slice, so adjust real prices by editing this table directly in
-- BigQuery until that's built.
CREATE TABLE `dbt-test-420614.lankabd_dataset.pricing_weights` (
  dimension STRING NOT NULL,
  key STRING NOT NULL,
  weight_price FLOAT64 NOT NULL
);

INSERT INTO `dbt-test-420614.lankabd_dataset.pricing_weights` (dimension, key, weight_price)
VALUES
  ('medium', 'telegram', 50.0),
  ('medium', 'whatsapp', 50.0),
  ('medium', 'email', 50.0),
  ('medium', 'web_push', 50.0),
  ('channel', 'alert', 100.0),
  ('channel', 'digest', 50.0);
