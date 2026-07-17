"""Shared scraper plumbing (ticket #47).

The three scrapers were seeded by copy-paste and carried ~35 byte-identical
lines each: the same HEADERS, the same retry policy, the same symbol lookup.
Verified by diff, not by eye — `get_symbols_from_sectors` was byte-identical
between announcement.py and priceArchive.py, and HEADERS was identical across
all three.

Deliberately **not** a BaseScraper. The three have genuinely different shapes —
dataGrid has no symbol fanout, announcement paginates and POSTs a CSRF token,
priceArchive GETs — and inheritance would force those into template-method
hooks and turn three readable scripts into one hierarchy. This is a module of
plain functions; the scrapers import what they need.
"""
import logging

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    from backend import db
except ImportError:  # standalone: the scrapers run with cwd=backend
    import db

logger = logging.getLogger(__name__)

BASE_URL = "https://lankabd.com"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Cache-Control': 'max-age=0',
}


def get_session() -> requests.Session:
    """A session that retries on the failures worth retrying.

    backoff_factor=1 means roughly 0s, 2s, 4s between attempts — lankabd.com is
    someone else's server, and 429 is in the list because it asks us to wait.
    """
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def get_date_range(years: int = 3) -> tuple[str, str]:
    """(from, to) as YYYY-MM-DD, spanning back `years` from today."""
    from datetime import datetime, timedelta

    today = datetime.now()
    start_date = today - timedelta(days=365 * years)
    return start_date.strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d')


def get_symbol_universe(sector: str | None = None) -> list[str]:
    """The symbols to scrape, from the datamatrix. Empty list on failure.

    This replaces two copies of an unfiltered lookup plus two more that built
    `WHERE Sector = '{sector}'` by interpolation. The sector is a query
    parameter now.

    Returns [] rather than raising because every caller already treats an empty
    universe as fatal and logs its own message — see scrape_all_* in
    priceArchive.py and announcement.py.
    """
    from google.cloud import bigquery

    sql = f"SELECT DISTINCT Symbol FROM {db.table_id('lankabd_datamatrix')} WHERE Symbol IS NOT NULL"
    params = []
    if sector:
        sql += " AND Sector = @sector"
        params.append(bigquery.ScalarQueryParameter("sector", "STRING", sector))

    try:
        symbols = [r["Symbol"] for r in db.query_rows(sql, params)]
    except Exception as e:
        logger.error(f"Error fetching symbols from BigQuery: {e}")
        return []

    where = f"in the {sector} sector" if sector else "in total"
    logger.info(f"Found {len(symbols)} symbols {where} from BigQuery datamatrix")
    return symbols
