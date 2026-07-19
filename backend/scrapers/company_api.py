"""Ingest ratios and financial statements from lankabd's company API (#58).

    python -m backend.scrapers.company_api          # from the repo root
    python scrapers/company_api.py                  # from backend/

The RATIO / FINANCIAL STATEMENT tabs on /Company/OverviewV2 are React widgets
that fetch JSON. A bare GET returns 400 with an empty body — a malformed
request, not a refusal: the API wants a `RequestVerificationToken` header, the
same CSRF pattern announcement.py already uses. With it, 200 and no account
(#32).

**The token is session-scoped, not per-company** — one page fetch covers all 414.

Two tables, both append-only (#52):

    fundamentals_ratios      symbol|year|code   — 23-ish ratios per year, 2023-25
    fundamentals_statements  symbol|year|fs_code — balance sheet / income / cash flow

**Long, not wide.** The ratio set varies by sector — GP reports 69 across 5
categories, AB Bank 33 across 3 — so a column per ratio would mean a schema
migration every time lankabd adds one, and #51 was exactly that pain.

**`code` is NOT a portable name for a metric**, contrary to what #58 assumed.
It is scoped to the sector: "Return on Assets (ROA)" arrives under 17 codes —
RTEXPIR0200 (textile), RENG0200 (engineering), RPHAR0200 (pharma), RBPIR0040
(bank), and so on. Across the corpus there are 312 codes but only 40 distinct
trimmed names. So `symbol|year|code` is a sound row key (verified unique live),
but anything asking "give me ROA for every company" — #59 — has to match on
name, and the names carry their own dirt ("Return on Asset (ROA)" singular for
non-bank financials). That mapping is a decision for #59, not something to
invent here.

`FSCode` (`BS96002`) joins the statements back to the equations behind each
ratio, and is not sector-scoped in the same way.

This is 2 requests per company, ~7 minutes at the usual politeness. Statements
only change when a company reports, so it belongs on a quarterly cadence (#55).
"""
import logging
import re
import time

from bs4 import BeautifulSoup

try:
    from backend import db
    from backend.scrapers.common import BASE, HEADERS, csrf_token, referer_headers, warm_session
except ImportError:  # standalone: cwd=backend
    import db
    from scrapers.common import BASE, HEADERS, csrf_token, referer_headers, warm_session

logger = logging.getLogger(__name__)

DATA_MATRIX = "/Home/DataMatrix"
RATIOS = "/api/company/FinancialRatiosV2"
STATEMENTS = "/api/company/FinancialStatementCollection"

# Politeness, matching the other scrapers. Applied per REQUEST — this makes two
# per company, so sleeping per company would halve it.
DELAY_SECONDS = 0.5
# Bank the work every N companies rather than buffering all 414.
BATCH_SIZE = 50
# How many years of statements to ask for. The ratios endpoint ignores it and
# returns three regardless.
STATEMENT_YEARS = 5


def open_session():
    """A session with cookies, plus the CSRF token the API requires.

    The token comes off any company page and works for every cid — it belongs to
    the session, not the company.
    """
    session = warm_session()
    token = csrf_token(session, f"{BASE}/Company/OverviewV2?cid=160", referer_headers())
    return session, token


def symbol_by_cid(session) -> dict[int, str]:
    """{cid: symbol} for every listed company, from one request.

    The DataMatrix page links each row to /Company/OverviewV2?cid=N with the
    ticker as the link text — 414 pairs, one cid each.
    """
    html = session.get(BASE + DATA_MATRIX, headers=referer_headers(), timeout=30).text

    out = {}
    for link in BeautifulSoup(html, "lxml").find_all("a", href=True):
        m = re.search(r"OverviewV2\?cid=(\d+)", link["href"])
        symbol = link.get_text(strip=True).upper()
        if m and symbol:
            out[int(m.group(1))] = symbol
    return out


def _api(session, token, path: str, cid: int, count: int | None = None):
    url = f"{BASE}{path}?cid={cid}" + (f"&count={count}" if count else "")
    resp = session.get(url, timeout=30, headers={
        **HEADERS,
        "RequestVerificationToken": token,
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json",
        "Referer": f"{BASE}/Company/OverviewV2?cid={cid}",
    })
    resp.raise_for_status()
    time.sleep(DELAY_SECONDS)  # per request, not per company: this is 2 per company
    return resp.json() if resp.text.strip() else None


def parse_ratios(symbol: str, payload) -> list[dict]:
    """Rows from a FinancialRatiosV2 response.

    An unknown cid, or a company with no financials (mutual funds), returns 200
    with empty ratioLists rather than an error — so an empty result is normal,
    not a failure.
    """
    rows = []
    for year_block in payload or []:
        year = year_block.get("year")
        if year is None:
            continue
        for r in year_block.get("ratioList") or []:
            code = r.get("Code")
            if not code:
                continue
            rows.append({
                "id": f"{symbol}|{year}|{code}",
                "symbol": symbol,
                "year": int(year),
                "code": code,
                # Stripped, not rewritten: the source emits both
                # "Return on Assets (ROA) " and "Return on Assets (ROA)".
                # Whitespace is lossless to remove; "Return on Asset (ROA)"
                # (singular, code RNB005) is left alone because collapsing it
                # would be a judgement, not a reading.
                "name": (r.get("Name") or "").strip(),
                "category": (r.get("Category") or "").strip(),
                "result": r.get("Result"),
                # The formula and its inputs — an audit trail for free, and the
                # only way to see WHY a ratio is what it is. GP's Gross Profit
                # Margin reads 1.0 because a telco has no COGS line; the
                # equation shows that rather than hiding it.
                "equation": r.get("Equation"),
                "base_equation": r.get("BaseEquation"),
            })
    return rows


def parse_statements(symbol: str, payload) -> list[dict]:
    """Rows from a FinancialStatementCollection response."""
    rows = []
    for r in payload or []:
        year, fs_code = r.get("Year"), r.get("FSCode")
        if year is None or not fs_code:
            continue
        rows.append({
            "id": f"{symbol}|{year}|{fs_code}",
            "symbol": symbol,
            "year": int(year),
            "fs_type": r.get("FSType"),       # Balance Sheet | Income Statement | Cash Flow Statement
            "fs_code": fs_code,               # BS96002 — joins to a ratio's base_equation
            "fs_key": (r.get("FSKey") or "").strip(),
            "fs_value": r.get("FSValue"),
            "fs_order": r.get("FSOrder"),
        })
    return rows


def ingest(limit: int | None = None) -> dict:
    """Scrape every company's ratios and statements. Returns counts.

    A company that fails is logged and skipped: this table is append-only, so a
    partial run adds facts without destroying any — unlike dataGrid, which
    replaces the symbol universe and therefore must refuse a partial scrape
    (#45).
    """
    session, token = open_session()
    cids = symbol_by_cid(session)
    if not cids:
        logger.error("No companies found on %s — cannot proceed.", DATA_MATRIX)
        return {"companies": 0, "ratios": 0, "statements": 0, "failed": 0}

    targets = sorted(cids.items())[:limit] if limit else sorted(cids.items())
    logger.info("Fetching ratios + statements for %d companies ...", len(targets))

    ratios, statements, failed = [], [], []
    counts = {"companies": len(targets), "ratios": 0, "statements": 0, "failed": 0}

    def flush():
        """Append what we have so far and let it go.

        Buffering all 414 companies and appending once at the end means a crash
        at company 400 writes nothing and throws away 828 requests. Append-only
        is the whole reason a partial run is safe (#52) — so actually bank the
        work as it arrives.
        """
        if ratios:
            db.append_version("fundamentals_ratios", ratios)
            counts["ratios"] += len(ratios)
            ratios.clear()
        if statements:
            db.append_version("fundamentals_statements", statements)
            counts["statements"] += len(statements)
            statements.clear()

    for i, (cid, symbol) in enumerate(targets, 1):
        try:
            company_ratios = parse_ratios(symbol, _api(session, token, RATIOS, cid))
            company_statements = parse_statements(
                symbol, _api(session, token, STATEMENTS, cid, count=STATEMENT_YEARS))
        except Exception as e:
            # Both endpoints or neither: a company whose statements failed after
            # its ratios succeeded must not land half-ingested and still be
            # counted as failed.
            logger.warning("[%d/%d] %s (cid=%d) failed: %s", i, len(targets), symbol, cid, e)
            failed.append(symbol)
            continue

        ratios.extend(company_ratios)
        statements.extend(company_statements)
        if i % BATCH_SIZE == 0:
            logger.info("  [%d/%d] %s — banking %d ratios, %d statements ...",
                        i, len(targets), symbol, len(ratios), len(statements))
            flush()

    flush()
    if failed:
        logger.warning("%d companies failed: %s", len(failed), ", ".join(failed[:10]))

    counts["failed"] = len(failed)
    return counts


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    counts = ingest()
    logger.info("Done: %s", counts)
    # Nothing scraped is a failed run, whichever endpoint came back empty.
    return 0 if counts["ratios"] and counts["statements"] else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
