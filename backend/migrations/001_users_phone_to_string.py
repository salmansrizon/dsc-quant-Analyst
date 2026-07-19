"""Migrate `users.phone` from INTEGER to STRING (ticket #51).

    python -m backend.migrations.001_users_phone_to_string          # from repo root
    python migrations/001_users_phone_to_string.py                  # from backend/
    ... --dry-run                                                   # report only

Signup returned 400 for every phone number in any dataset where `phone` is
INTEGER:

    Could not convert '01700000000' with type str: tried to convert to int64

The column was autodetected from load-job data that happened to look numeric,
while `models.UserCreate` types phone as a string. Every Bangladeshi mobile
number starts with 0, so a leading-zero string can never convert to int64.

`bootstrap_tables.py` declares phone as STRING, but only for tables it CREATES —
it cannot change an existing column's type. Hence this script. Any deployment
that predates it needs this run once.

**This does not recover the leading zeros.** A phone stored as INTEGER already
lost its leading 0 on write (`01700000001` became `1700000001`); casting fixes
the type, not the digit. Prepending a '0' would be inventing data, so old rows
stay visibly wrong and new signups are correct.

Idempotent: exits cleanly if phone is already STRING.

Safety: BigQuery cannot ALTER INT64 -> STRING in place, so the table is rebuilt
by a query job with a destination (allowed on the free tier; DML is not). That
rewrite drops any row appended while it runs — the same hazard as #40 — so it
takes a backup first and should be run with writes quiesced.
"""
import argparse
import logging
import os
import sys

from google.cloud import bigquery

# This lives one level deeper than the other scripts, so neither `backend` nor a
# bare `db` is importable by default — put the repo root on the path first.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend import db  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

TABLE = "users"
BACKUP = "users_backup_pre51"
COLUMNS = [
    "id", "email", "password_hash", "full_name", "role",
    "created_at", "updated_at", "is_deleted",
]


def phone_type() -> str | None:
    """The live type of users.phone, or None if the table/column is absent."""
    try:
        schema = db.client().get_table(db.qualified_name(TABLE)).schema
    except Exception:
        return None
    for field in schema:
        if field.name == "phone":
            return field.field_type
    return None


def migrate(dry_run: bool = False) -> bool:
    """Returns whether the table was changed."""
    current = phone_type()
    if current is None:
        logger.info("No users table (or no phone column) — nothing to migrate.")
        return False
    if current == "STRING":
        logger.info("users.phone is already STRING — nothing to do.")
        return False

    logger.warning("users.phone is %s; signup is broken until this is fixed.", current)
    if dry_run:
        logger.info("--dry-run: stopping before any write.")
        return False

    client = db.client()
    before = len(db.query_rows(f"SELECT id FROM {db.table_id(TABLE)}"))

    logger.info("Backing up %d rows to %s ...", before, BACKUP)
    client.query(
        f"SELECT * FROM {db.table_id(TABLE)}",
        job_config=bigquery.QueryJobConfig(
            destination=db.qualified_name(BACKUP),
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        ),
    ).result()

    # Every version row is preserved: this table is an append-only log (#52).
    projection = ", ".join(COLUMNS[:2] + ["CAST(phone AS STRING) AS phone"] + COLUMNS[2:])
    logger.info("Rebuilding %s with phone as STRING ...", TABLE)
    client.query(
        f"SELECT {projection} FROM {db.table_id(TABLE)}",
        job_config=bigquery.QueryJobConfig(
            destination=db.qualified_name(TABLE),
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        ),
    ).result()

    after = len(db.query_rows(f"SELECT id FROM {db.table_id(TABLE)}"))
    if after != before:
        raise RuntimeError(
            f"Row count changed: {before} -> {after}. {BACKUP} holds the original."
        )

    db.ensure_current_view(TABLE, key=db.VERSIONED_TABLES[TABLE])
    logger.info("Done: %d rows, phone is %s, %s_current rebuilt.",
                after, phone_type(), TABLE)
    logger.info("Backup left at %s — drop it once you are satisfied.", BACKUP)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would change, write nothing")
    args = parser.parse_args()
    try:
        migrate(dry_run=args.dry_run)
    except Exception as e:
        logger.error("Migration failed: %s", e)
        sys.exit(1)
