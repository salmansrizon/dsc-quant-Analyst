"""Shared scraper plumbing: HTTP session, date range, symbol universe (#47).

Not a BaseScraper: the three scrapers have genuinely different shapes — dataGrid
has no symbol fanout, announcement paginates and POSTs a CSRF token,
priceArchive GETs — so inheritance would force those differences into
template-method hooks. Plain functions, imported.
"""
import logging
from datetime import datetime, timedelta

import requests
from google.cloud import bigquery
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    from backend import db
except ImportError:  # standalone: the scrapers run with cwd=backend
    import db

_logger = logging.getLogger(__name__)

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

    backoff_factor=1 gives roughly 0s, 2s, 4s between attempts. 429 is in the
    list because the server is asking us to wait.
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
    today = datetime.now()
    start_date = today - timedelta(days=365 * years)
    return start_date.strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d')


def get_symbol_universe(sector: str | None = None, logger=None) -> list[str]:
    """The symbols to scrape, from the datamatrix. Empty list on failure.

    `logger` takes the caller's utils.logger.Log so these lines reach the run's
    logfile. Without it they go to a module logger that has no handlers, which
    means the message explaining why a scrape found zero symbols never appears.

    Returns [] rather than raising because every caller already treats an empty
    universe as fatal and logs its own message — see scrape_all_* in
    priceArchive.py and announcement.py. The cost: an outage and a genuinely
    empty sector are indistinguishable to the caller.
    """
    log = logger or _logger

    sql = f"SELECT DISTINCT Symbol FROM {db.table_id('lankabd_datamatrix')} WHERE Symbol IS NOT NULL"
    params = []
    if sector:
        sql += " AND Sector = @sector"
        params.append(bigquery.ScalarQueryParameter("sector", "STRING", sector))

    try:
        symbols = [r["Symbol"] for r in db.query_rows(sql, params)]
    except Exception as e:
        log.error(f"Error fetching symbols from BigQuery: {e}")
        return []

    where = f"in the {sector} sector" if sector else "in total"
    log.info(f"Found {len(symbols)} symbols {where} from BigQuery datamatrix")
    return symbols
