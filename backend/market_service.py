"""Read-only market-data queries (split from the bq_service god module, #43)."""
from itertools import groupby

from google.cloud import bigquery

from . import db
from . import indicators
from . import price_series


def list_sectors():
    sql = f"""
        SELECT Sector,
               COUNT(*) AS stock_count,
               ROUND(AVG(LTP), 2) AS avg_ltp,
               ROUND(AVG(__Change), 2) AS avg_change,
               SUM(Volume_Qty_) AS total_volume,
               ROUND(SUM(Value_Turnover_), 2) AS total_turnover
        FROM {db.table_id('lankabd_datamatrix')}
        WHERE Sector IS NOT NULL AND Sector != ''
        GROUP BY Sector
        ORDER BY Sector
    """
    return db.query_rows(sql)


def list_stocks(sector: str = None, search: str = None, limit: int = 500):
    wheres = []
    if sector:
        wheres.append("Sector = @sector")
    if search:
        wheres.append("LOWER(Symbol) LIKE @search")
    where = " AND ".join(wheres) if wheres else "TRUE"
    params = [
        bigquery.ScalarQueryParameter("sector", "STRING", sector) if sector else None,
        bigquery.ScalarQueryParameter("search", "STRING", f"%{search.lower()}%") if search else None,
    ]
    params = [p for p in params if p is not None]

    sql = f"""
        SELECT Symbol, Sector, LTP, Open, High, Low, Close, YCP,
               ROUND(Change, 2) AS Change, ROUND(__Change, 2) AS ChangePct,
               Volume_Qty_, Value_Turnover_, EPS
        FROM {db.table_id('lankabd_datamatrix')}
        WHERE {where}
        ORDER BY Symbol
        LIMIT {int(limit)}
    """
    return db.query_rows(sql, params)


def get_stock(symbol: str):
    sql = f"""
        SELECT Symbol, Sector, LTP, Open, High, Low, Close, YCP,
               ROUND(Change, 2) AS Change, ROUND(__Change, 2) AS ChangePct,
               Volume_Qty_, Value_Turnover_, EPS
        FROM {db.table_id('lankabd_datamatrix')}
        WHERE Symbol = @symbol
        LIMIT 1
    """
    params = [bigquery.ScalarQueryParameter("symbol", "STRING", symbol.upper())]
    rows = db.query_rows(sql, params)
    return rows[0] if rows else None


def top_movers(limit: int = 10):
    sql = f"""
        SELECT Symbol, Sector, LTP, ROUND(__Change, 2) AS ChangePct
        FROM {db.table_id('lankabd_datamatrix')}
        ORDER BY __Change DESC
        LIMIT {int(limit)}
    """
    gainers = db.query_rows(sql)

    sql = f"""
        SELECT Symbol, Sector, LTP, ROUND(__Change, 2) AS ChangePct
        FROM {db.table_id('lankabd_datamatrix')}
        ORDER BY __Change ASC
        LIMIT {int(limit)}
    """
    losers = db.query_rows(sql)

    return {"gainers": gainers, "losers": losers}


def price_history(symbol: str, days: int = 365):
    # DISTINCT because lankabd_price_archive stores every (Symbol, Date) twice
    # (#64); without it LIMIT counts doubled rows and returns ~half the days.
    # price_series dedupes again defensively for partial (non-identical) dupes.
    sql = f"""
        SELECT DISTINCT Date, Symbol, LTP, High, Low, OPENP_ AS Open, Close, YCP,
               ROUND(Change__, 2) AS ChangePct, Volume_Qty_ AS Volume,
               SMA_20, RSI
        FROM {db.table_id('lankabd_price_archive')}
        WHERE Symbol = @symbol
        ORDER BY Date DESC
        LIMIT {int(days)}
    """
    params = [bigquery.ScalarQueryParameter("symbol", "STRING", symbol.upper())]
    return db.query_rows(sql, params)


def _bonus_factors(symbol: str) -> list[tuple]:
    """Bonus/stock-dividend price-adjustment factors for one symbol (#63).

    Cash-only declarations and rows with no record_date are filtered by
    `price_series.adjustment_factors` itself; this just supplies the raw
    declarations from the one table that has them.
    """
    sql = f"""
        SELECT record_date, stock_dividend_pct
        FROM {db.current_view('fundamentals_dividends')}
        WHERE symbol = @symbol AND stock_dividend_pct IS NOT NULL AND stock_dividend_pct > 0
    """
    params = [bigquery.ScalarQueryParameter("symbol", "STRING", symbol.upper())]
    return price_series.adjustment_factors(db.query_rows(sql, params))


def technical_indicators(symbol: str, days: int = 365):
    """Compute the v1 technical-indicator bundle (spec 4) from price history.

    Indicators are computed on-read in Python rather than stored in a
    precomputed BigQuery table — see ticket #31. This is the canonical indicator
    source; the raw SMA_20/RSI columns in lankabd_price_archive are left as
    scraped passthrough on price_history and are not reconciled here.

    Prices are adjusted on-read for bonus/stock-dividend actions (#63) before
    indicators.py ever sees them — a 50% bonus otherwise reads as a -31% crash
    (EASTRNLUB, 2025-12-23). indicators.py never learns adjustment exists.
    """
    rows = price_history(symbol, days=days)
    factors = _bonus_factors(symbol)
    closes, highs, lows, volumes = price_series.from_price_history(rows, factors)
    if not closes:
        return {"symbol": symbol.upper(), "indicators": None, "points": 0}

    bundle = indicators.compute_all(closes, highs, lows, volumes)
    return {"symbol": symbol.upper(), "points": len(closes), "indicators": bundle}


def list_announcements(symbol: str = None, limit: int = 50):
    wheres = []
    params = []
    if symbol:
        wheres.append("Symbol = @symbol")
        params.append(bigquery.ScalarQueryParameter("symbol", "STRING", symbol.upper()))

    where = " AND ".join(wheres) if wheres else "TRUE"
    sql = f"""
        SELECT Symbol, Date, Announcement_Type, Details, Sentiment,
               Expected_Price_Impact, Importance, Sector
        FROM {db.table_id('lankabd_announcements')}
        WHERE {where}
        ORDER BY Date DESC
        LIMIT {int(limit)}
    """
    return db.query_rows(sql, params)


def market_summary():
    sql = f"""
        SELECT COUNT(*) AS total_stocks,
               COUNT(DISTINCT Sector) AS total_sectors,
               ROUND(AVG(LTP), 2) AS avg_price,
               ROUND(SUM(Value_Turnover_), 2) AS total_turnover,
               MAX(updated_at) AS last_updated
        FROM {db.table_id('lankabd_datamatrix')}
    """
    rows = db.query_rows(sql)
    return rows[0] if rows else {}


# ── Dashboard leaderboards (PRD-12, ported from main onto append-only reads, #82)
#
# All pure on-read queries over lankabd_datamatrix / lankabd_price_archive — no
# cache tables. main backed these with refresh_cache.py's CREATE OR REPLACE
# TABLE jobs; that DDL is redundant here (the free tier is append-only, and
# list_sectors/market_summary already compute the same aggregates on-read — see
# [[bigquery-free-tier-no-dml]]), so refresh_cache is intentionally not ported.
#
# The extremes/technical leaderboards read datamatrix columns that only land
# once dataGrid's widened allowlist re-scrapes: NAV_Quarter_End_, Audited_PE,
# Director_Holdings, RSI_14_. Until that scrape runs, those columns do not exist
# on the live table, so BigQuery fails these queries at compile time (a 5xx) —
# they are NOT gracefully empty. The re-scrape is the load-bearing prerequisite
# (#82 comment); wiring the extremes UI before it would surface those errors.
# `leaderboard`, `market_strength` and `sector_breakdown` read only pre-existing
# columns and work today (sector_breakdown's AVG(Audited_PE) needs the scrape).

_LEADERBOARD_COLUMNS = {
    "value": ("Value_Turnover_", "DESC"),
    "gainer": ("__Change", "DESC"),
    "loser": ("__Change", "ASC"),
    "volume": ("Volume_Qty_", "DESC"),
}


def leaderboard(metric: str, limit: int = 10):
    """Top-N by a raw datamatrix column (value/gainer/loser/volume), or by the
    latest trade count from price_archive (`trade`)."""
    if metric == "trade":
        return top_trade(limit)
    column, direction = _LEADERBOARD_COLUMNS[metric]
    sql = f"""
        SELECT Symbol, Sector, LTP, ROUND(__Change, 2) AS ChangePct,
               Volume_Qty_ AS Volume, Value_Turnover_ AS Value
        FROM {db.table_id('lankabd_datamatrix')}
        ORDER BY {column} {direction}
        LIMIT {int(limit)}
    """
    return db.query_rows(sql)


def top_trade(limit: int = 10):
    sql = f"""
        WITH latest_trade AS (
            SELECT Symbol, Trade FROM (
                SELECT Symbol, SAFE_CAST(Trade AS INT64) AS Trade,
                       ROW_NUMBER() OVER (PARTITION BY Symbol ORDER BY Date DESC) AS rn
                FROM {db.table_id('lankabd_price_archive')}
                WHERE SAFE_CAST(Trade AS INT64) IS NOT NULL
            )
            WHERE rn = 1
        )
        SELECT d.Symbol, d.Sector, d.LTP, ROUND(d.__Change, 2) AS ChangePct,
               d.Volume_Qty_ AS Volume, d.Value_Turnover_ AS Value, lt.Trade
        FROM {db.table_id('lankabd_datamatrix')} d
        JOIN latest_trade lt ON d.Symbol = lt.Symbol
        ORDER BY lt.Trade DESC
        LIMIT {int(limit)}
    """
    return db.query_rows(sql)


_EXTREMES_COLUMNS = {
    "pe_low": ("Audited_PE", "ASC"),
    "pe_high": ("Audited_PE", "DESC"),
    "director_holding_low": ("Director_Holdings", "ASC"),
    "director_holding_high": ("Director_Holdings", "DESC"),
}


def extremes_leaderboard(metric: str, limit: int = 10):
    """Fundamental extremes: PE / director-holding rankings, plus a derived
    NAV-to-price ratio (`nav_price_*`) computed in SQL."""
    if metric in ("nav_price_low", "nav_price_high"):
        direction = "ASC" if metric == "nav_price_low" else "DESC"
        sql = f"""
            SELECT Symbol, Sector, LTP,
                   ROUND(SAFE_DIVIDE(NAV_Quarter_End_, LTP), 2) AS MetricValue
            FROM {db.table_id('lankabd_datamatrix')}
            WHERE NAV_Quarter_End_ IS NOT NULL AND LTP IS NOT NULL AND LTP != 0
            ORDER BY MetricValue {direction}
            LIMIT {int(limit)}
        """
        return db.query_rows(sql)
    column, direction = _EXTREMES_COLUMNS[metric]
    sql = f"""
        SELECT Symbol, Sector, LTP, {column} AS MetricValue
        FROM {db.table_id('lankabd_datamatrix')}
        WHERE {column} IS NOT NULL
        ORDER BY {column} {direction}
        LIMIT {int(limit)}
    """
    return db.query_rows(sql)


def market_strength():
    """Breadth: how many symbols are up / down / flat on the day."""
    sql = f"""
        SELECT
            COUNTIF(__Change > 0) AS Gainers,
            COUNTIF(__Change < 0) AS Losers,
            COUNTIF(__Change = 0) AS Unchanged
        FROM {db.table_id('lankabd_datamatrix')}
    """
    rows = db.query_rows(sql)
    return rows[0] if rows else {}


def sector_breakdown():
    """Per-sector PE, traded value, gainer/loser counts and average change."""
    sql = f"""
        SELECT
            Sector,
            ROUND(AVG(Audited_PE), 2) AS AvgPE,
            ROUND(SUM(Value_Turnover_), 2) AS TotalTradeValue,
            COUNTIF(__Change > 0) AS GainersCount,
            COUNTIF(__Change < 0) AS LosersCount,
            ROUND(AVG(__Change), 2) AS AvgChange
        FROM {db.table_id('lankabd_datamatrix')}
        WHERE Sector IS NOT NULL AND Sector != ''
        GROUP BY Sector
        ORDER BY Sector
    """
    return db.query_rows(sql)


_TECHNICAL_COMPUTED = {
    "macd_low": ("macd", "ASC"),
    "macd_high": ("macd", "DESC"),
    "stochastic_low": ("stochastic", "ASC"),
    "stochastic_high": ("stochastic", "DESC"),
}


def technical_extremes(metric: str, limit: int = 10):
    """Technical-indicator extremes. `rsi_*` reads the scraped RSI_14_ column;
    `macd_*` / `stochastic_*` are computed on-read (like technical_indicators,
    #31) from the last 50 price_archive bars per symbol — the raw table has no
    MACD/stochastic column, so there is nothing to read."""
    if metric in ("rsi_low", "rsi_high"):
        direction = "ASC" if metric == "rsi_low" else "DESC"
        sql = f"""
            SELECT Symbol, Sector, LTP, RSI_14_ AS MetricValue
            FROM {db.table_id('lankabd_datamatrix')}
            WHERE RSI_14_ IS NOT NULL
            ORDER BY RSI_14_ {direction}
            LIMIT {int(limit)}
        """
        return db.query_rows(sql)

    indicator, direction = _TECHNICAL_COMPUTED[metric]
    # Sector/LTP come from the datamatrix join so we don't assume the price
    # archive carries them; bars are ordered ascending per symbol for the series.
    sql = f"""
        WITH ranked AS (
            SELECT Symbol, Date, High, Low, Close,
                   ROW_NUMBER() OVER (PARTITION BY Symbol ORDER BY Date DESC) AS rn
            FROM {db.table_id('lankabd_price_archive')}
            WHERE Close IS NOT NULL AND High IS NOT NULL AND Low IS NOT NULL
        )
        SELECT r.Symbol, d.Sector, d.LTP, r.Date, r.High, r.Low, r.Close
        FROM ranked r
        JOIN {db.table_id('lankabd_datamatrix')} d ON r.Symbol = d.Symbol
        WHERE r.rn <= 50
        ORDER BY r.Symbol, r.Date ASC
    """
    rows = db.query_rows(sql)

    results = []
    for symbol, group_iter in groupby(rows, key=lambda r: r["Symbol"]):
        group = list(group_iter)
        closes = [r["Close"] for r in group]
        if indicator == "macd":
            triple = indicators.macd(closes)
            latest = triple["macd"] if triple else None
        else:
            highs = [r["High"] for r in group]
            lows = [r["Low"] for r in group]
            latest = indicators.stochastic(highs, lows, closes)
        if latest is None:
            continue
        last_row = group[-1]
        results.append({
            "Symbol": symbol,
            "Sector": last_row["Sector"],
            "LTP": last_row["LTP"],
            "MetricValue": round(latest, 2),
        })

    results.sort(key=lambda r: r["MetricValue"], reverse=(direction == "DESC"))
    return results[:limit]
