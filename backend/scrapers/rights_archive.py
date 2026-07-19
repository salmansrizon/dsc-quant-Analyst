"""Ingest /Home/RightArchive — rights issues (#65, from #33).

    python -m scrapers.rights_archive          # from backend/

One public page, no token, ~100+ rows: Symbol, Right Offer ("1R:2"), Issue
Price, Right Premium, Record Date, Year, Subscription Open/Close. Lands in the
append-only `rights_archive` table.

**Ingest-only.** The v2 ex-rights price adjustment is deferred (#33): it needs
the theoretical ex-rights price (subscription price + ratio), not a single
factor like a bonus. This just gets the data into BigQuery so that work has
something to read.

Parsing reuses the shared scraper plumbing (#47/#60): the CSRF-free page is one
GET, and header_keyed_rows does the table zip.
"""
import logging
import re
from datetime import datetime

try:
    from backend import db
    from backend.scrapers.common import BASE, referer_headers, warm_session, biggest_table, header_keyed_rows
except ImportError:  # standalone: cwd=backend
    import db
    from scrapers.common import BASE, referer_headers, warm_session, biggest_table, header_keyed_rows

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Both "1R:2" and "1:17" appear in the archive — the R is optional.
_RATIO = re.compile(r"(\d+)\s*R?\s*:\s*(\d+)")


def _to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _to_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _to_date(v):
    """'07-Mar-2024' -> a date, or None. The archive writes '-' and '' for absent."""
    if not v or v.strip() in ("-", ""):
        return None
    try:
        return datetime.strptime(v.strip(), "%d-%b-%Y").date()
    except ValueError:
        return None


def _ratio(right_offer: str) -> tuple[int | None, int | None]:
    """'1R:2' (also '1R: 2') -> (1, 2): one new share offered per two held."""
    m = _RATIO.search(right_offer or "")
    if not m:
        return None, None
    return int(m.group(1)), int(m.group(2))


def parse_rights(html: str) -> list[dict]:
    """Normalized rights-issue rows from the archive page (pure, testable).

    Skips rows with no symbol or no record_date — without a record_date a rights
    issue can't be placed in time, which is the whole point for the v2 adjustment.
    """
    out = []
    for row in header_keyed_rows(biggest_table(html)):
        symbol = (row.get("Symbol") or "").strip().upper()
        record_date = _to_date(row.get("Record Date"))
        if not symbol or record_date is None:
            continue
        new, held = _ratio(row.get("Right Offer"))
        out.append({
            "id": f"{symbol}|{record_date.isoformat()}",
            "symbol": symbol,
            "right_offer": (row.get("Right Offer") or "").strip(),
            "offer_new": new,
            "offer_held": held,
            "issue_price": _to_float(row.get("Issue Price")),
            "right_premium": _to_float(row.get("Right Premium")),
            "record_date": record_date,
            "year": _to_int(row.get("Year")),
            "subscription_open": _to_date(row.get("Subscription Open Date")),
            "subscription_close": _to_date(row.get("Subscription Close Date")),
            "source": "right_archive",
            "is_deleted": False,
        })
    return out


def ingest() -> int:
    """Fetch and append the rights archive. Returns the row count."""
    session = warm_session()
    resp = session.get(f"{BASE}/Home/RightArchive", headers=referer_headers(), timeout=30)
    resp.raise_for_status()
    rows = parse_rights(resp.text)
    if not rows:
        logger.warning("RightArchive parsed to zero rows — the markup may have changed.")
        return 0
    db.append_version("rights_archive", rows)
    logger.info("Ingested %d rights issues.", len(rows))
    return len(rows)


def main() -> int:
    return 0 if ingest() >= 0 else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
