-- One-time migration: add last_digest_sent_at to subscription_packages so the
-- digest dispatcher can track when each subscription last received a digest,
-- to honor alternate/weekly cadences (vs. daily, which needs no tracking).
-- Explicit ALTER TABLE, not relying on _insert_rows' dataframe-autodetect
-- (ALLOW_FIELD_ADDITION) — see migration 07 for why: a column whose first-ever
-- insert is NULL is especially likely to get its type inferred wrong.
ALTER TABLE `dbt-test-420614.lankabd_dataset.subscription_packages`
ADD COLUMN IF NOT EXISTS last_digest_sent_at TIMESTAMP;
