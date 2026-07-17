"""Ingest reported fundamentals from lankabd's public pages (ticket #57).

Two pages, one request each, no auth and no CSRF token:

  /Home/DividendArchive     4,396 rows, 432 symbols, 2014-2026 — weekly
  /Details/GetLatestEarnings  410 rows, one per symbol, live  — daily

They feed two tables, because the data carries two concepts and merging them
loses rows (see the grain note below):

  fundamentals_earnings    EPS/NAV per symbol per reporting period
  fundamentals_dividends   one row per dividend declaration

**Grain matters here.** `Dividend Type` is a *declaration* type
(Interim/Final/Annual), not a reporting period, and a company declares several
per year. Keying on symbol|year drops all but one, because the append-only
`_current` view keeps the last row per id (#52). Declarations are keyed
symbol|year|type|publish_date; earnings symbol|year|period|publish_date.

EPS/NAV ride on whichever declaration reported them, and the span they cover is
read from the type where it states one — see `archive_period`. The archive is
where the long EPS history comes from; GetLatestEarnings only ever holds the
current period.
"""
import logging
import re
from datetime import date, datetime

from bs4 import BeautifulSoup

try:
    from backend import db
    from backend.scrapers.common import BASE, referer_headers, warm_session
except ImportError:  # standalone: cwd=backend
    import db
    from scrapers.common import BASE, referer_headers, warm_session

logger = logging.getLogger(__name__)

DIVIDEND_ARCHIVE = "/Home/DividendArchive"
LATEST_EARNINGS = "/Details/GetLatestEarnings"

# The archive's free-text `Dividend Type`, normalised. Every key below was
# observed live — including the typo. The raw string is always kept alongside.
_DIVIDEND_TYPES = {
    "annual": "ANNUAL",
    "annuall": "ANNUAL",              # sic
    "annual (11 months)": "ANNUAL",
    "annual (14 months)": "ANNUAL",
    "annual (18 months)": "ANNUAL",
    "12 months": "ANNUAL",
    "semi-annual": "SEMI_ANNUAL",
    "semi annual": "SEMI_ANNUAL",
    "semi- annual": "SEMI_ANNUAL",
    "half yearly": "SEMI_ANNUAL",
    "06 months": "SEMI_ANNUAL",
    "interim": "INTERIM",
    "interim (12 months)": "INTERIM",
    "final": "FINAL",
    "final (06 months)": "FINAL",
}

# GetLatestEarnings' `Annual/Quarter`, normalised.
_PERIODS = {
    "annual": "ANNUAL",
    "half yearly": "H1",
    "1st quarter": "Q1",
    "2nd quarter": "Q2",
    "3rd quarter": "Q3",
    "nine months": "9M",
}


def normalise_dividend_type(raw: str) -> str:
    """ANNUAL | SEMI_ANNUAL | INTERIM | FINAL | UNKNOWN.

    754 archive rows have a blank type; they are not errors, so they get
    UNKNOWN rather than being dropped.
    """
    key = re.sub(r"\s+", " ", (raw or "").strip().lower())
    if not key:
        return "UNKNOWN"
    return _DIVIDEND_TYPES.get(key, "UNKNOWN")


def normalise_period(raw: str) -> str:
    """ANNUAL | H1 | Q1 | Q2 | Q3 | 9M | UNKNOWN."""
    key = re.sub(r"\s+", " ", (raw or "").strip().lower())
    return _PERIODS.get(key, "UNKNOWN")


_MONTHS = re.compile(r"(?:\(|^)\s*(\d+)\s*months?\s*\)?", re.I)


def archive_period(raw: str) -> str:
    """The span an archive row's EPS/NAV covers: ANNUAL | H1 | <n>M | UNKNOWN.

    A stated month count is reported verbatim as "<n>M" and never aliased.
    MJLBD 2016 shows why: it reports 7.72 over "Annual (18 Months)", 4.18 over
    "Interim (12 Months)" and 3.48 over "Final (06 Months)" — and 4.18 + 3.48 =
    7.66, so the parts sum to the whole and the months are the *coverage*. But
    that also means the 12-month figure is NOT the annual one here: the fiscal
    year is 18 months long. Mapping 12 -> ANNUAL would hand #59 an interim
    figure to compute PEG from. Say "12M" and let the caller decide.

    A blank type maps to ANNUAL. That is an inference, not a reading: all 747
    blank rows are 2014-16, each is the only EPS record for its symbol-year, and
    none shares a symbol-year with a typed row. `period_raw` keeps the empty
    string, so the inference stays auditable and reversible.

    UNKNOWN is reserved for rows that genuinely do not say — a bare "Interim" or
    "Final" with no month count.
    """
    text = re.sub(r"\s+", " ", (raw or "").strip())
    m = _MONTHS.search(text)
    if m:
        return f"{int(m.group(1))}M"

    kind = normalise_dividend_type(text)
    if kind == "ANNUAL":
        return "ANNUAL"
    if kind == "SEMI_ANNUAL":
        return "H1"
    if not text:
        return "ANNUAL"  # see the docstring — inferred, not stated
    return "UNKNOWN"


def parse_number(raw: str) -> float | None:
    """The pages use '-' and '' for missing, and thousands separators."""
    if raw is None:
        return None
    text = raw.strip().replace(",", "")
    if text in ("", "-", "N/A", "n/a"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_date(raw: str) -> date | None:
    """The two pages disagree on format: '15-Sep-2024' vs '2026-07-16'.

    Returns a `date`, not an ISO string: these land in BigQuery DATE columns via
    a load job, and pyarrow will not coerce str -> date. That mismatch is
    exactly what broke signup in #51.
    """
    text = (raw or "").strip()
    if text in ("", "-"):
        return None
    for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%d-%B-%Y", "%d %b, %Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    logger.warning("Unparseable date %r", text)
    return None


def _row_id(symbol: str, year: int, discriminator: str, publish: date | None) -> str:
    """The composite key. `publish` is part of it because one symbol-year can
    hold several declarations (MARICO 2026 has five) and several reporting
    periods (MJLBD 2016 has three) — and the append-only `_current` view keeps
    only the last row per id (#52), so a lossy key silently drops facts.
    """
    return f"{symbol}|{year}|{discriminator}|{publish or 'nodate'}"


def _biggest_table(html: str):
    tables = BeautifulSoup(html, "lxml").find_all("table")
    if not tables:
        return None
    return max(tables, key=lambda t: len(t.find_all("tr")))


def _rows(html: str) -> list[dict]:
    """Header-keyed dicts from the page's largest table."""
    table = _biggest_table(html)
    if table is None:
        return []
    headers = [th.get_text(strip=True) for th in table.find_all("th")]
    if not headers:
        return []
    out = []
    for tr in table.find_all("tr")[1:]:
        cells = [td.get_text(strip=True) for td in tr.find_all("td")]
        if len(cells) == len(headers):
            out.append(dict(zip(headers, cells)))
    return out


def parse_dividend_archive(html: str) -> tuple[list[dict], list[dict]]:
    """(dividend rows, earnings rows) from the archive page.

    One page feeds both tables: every row is a declaration, and the rows that
    carry EPS/NAV are also the annual earnings history.
    """
    dividends, earnings = [], []
    for r in _rows(html):
        symbol = r.get("Symbol", "").strip().upper()
        year = parse_number(r.get("Year"))
        if not symbol or year is None:
            continue
        year = int(year)

        raw_type = r.get("Dividend Type", "")
        div_type = normalise_dividend_type(raw_type)
        publish = parse_date(r.get("Dividend PublishDate in DSE"))

        dividends.append({
            "id": _row_id(symbol, year, div_type, publish),
            "symbol": symbol,
            "sector": r.get("Sector", "").strip(),
            "year": year,
            "dividend_type": div_type,
            "dividend_type_raw": raw_type,
            "cash_dividend_pct": parse_number(r.get("Cash Dividend %")),
            "stock_dividend_pct": parse_number(r.get("RIU/Stock Dividend %")),
            "publish_date": publish,
            "record_date": parse_date(r.get("Record Date")),
            "agm_date": parse_date(r.get("AGM Date")),
            "year_end_date": parse_date(r.get("Year End Date")),
            "source": "dividend_archive",
        })

        # EPS/NAV ride on the declaration that reported them.
        eps, nav = parse_number(r.get("EPS/EPU")), parse_number(r.get("NAV"))
        if eps is not None or nav is not None:
            period = archive_period(raw_type)
            earnings.append({
                "id": _row_id(symbol, year, period, publish),
                "symbol": symbol,
                "sector": r.get("Sector", "").strip(),
                "year": year,
                "period": period,
                "period_raw": raw_type,
                "eps": eps,
                "nav": nav,
                "publish_date": publish,
                "source": "dividend_archive",
            })
    return dividends, earnings


def parse_latest_earnings(html: str) -> list[dict]:
    """Earnings rows from the latest-earnings page."""
    out = []
    for r in _rows(html):
        symbol = r.get("Symbol", "").strip().upper()
        year = parse_number(r.get("Year"))
        if not symbol or year is None:
            continue
        year = int(year)
        raw_period = r.get("Annual/Quarter", "")
        publish = parse_date(r.get("Publish Date"))
        period = normalise_period(raw_period)
        out.append({
            "id": _row_id(symbol, year, period, publish),
            "symbol": symbol,
            "sector": r.get("Sector", "").strip(),
            "year": year,
            "period": period,
            "period_raw": raw_period,
            "eps": parse_number(r.get("EPS/EPU")),
            "nav": parse_number(r.get("NAV")),
            "publish_date": publish,
            "source": "latest_earnings",
        })
    return out


def _fetch(path: str) -> str:
    session = warm_session()
    resp = session.get(BASE + path, headers=referer_headers(), timeout=30)
    resp.raise_for_status()
    return resp.text


def ingest() -> dict:
    """Scrape both pages and append what they hold. Returns row counts.

    #57 asked which source should win when they disagree. **They do not
    collide, so nothing has to win.** The two `publish_date`s are different
    events — the archive's is when a dividend was declared to the DSE, the
    earnings page's is when a result was reported — so two rows describing the
    same symbol-year-period still carry different ids and both survive as
    distinct facts. A caller that wants one figure per period picks by `source`.

    That is the honest answer to the question, rather than the arbitration the
    ticket assumed it needed.
    """
    logger.info("Fetching %s ...", DIVIDEND_ARCHIVE)
    dividends, archive_earnings = parse_dividend_archive(_fetch(DIVIDEND_ARCHIVE))
    logger.info("  %d dividend declarations, %d annual earnings rows",
                len(dividends), len(archive_earnings))

    logger.info("Fetching %s ...", LATEST_EARNINGS)
    latest = parse_latest_earnings(_fetch(LATEST_EARNINGS))
    logger.info("  %d latest-earnings rows", len(latest))

    if dividends:
        db.append_version("fundamentals_dividends", dividends)
    # Archive first, latest second: the fresher figure wins on a shared id.
    if archive_earnings or latest:
        db.append_version("fundamentals_earnings", archive_earnings + latest)

    return {
        "dividends": len(dividends),
        "earnings_archive": len(archive_earnings),
        "earnings_latest": len(latest),
    }


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    counts = ingest()
    logger.info("Done: %s", counts)
    # A scrape that returned nothing is a failed run, whichever page came back
    # empty — a scheduler reads the exit code, not the log.
    return 0 if all(counts.values()) else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
