"""Behaviour-driven affinity (#107, seam fixed by #93/#96 → #86's rollup).

Turns #86's `behaviour_summary` rollup — per-user, per-(symbol|sector) interest,
already normalized 0..1 and time-decayed, standing portfolio/watchlist signal
baked in — into the bounded [0,1] tilt #93's `_rank` multiplies into a small
ranking bonus (fit stays the spine, this only tilts it — #93 decision). Direct
engagement with the candidate itself outweighs merely having browsed its sector:
0.7×symbol + 0.3×sector, capped at 1.0. A candidate with no recorded interest —
symbol or sector — scores 0.0, so a cold-start user's ranking falls back to pure
fit, per the ticket's requirement.

`behaviour_summary` only changes once a day (#86's nightly rollup), so the
per-user row fetch is memoized rather than re-read on every candidate in a
`recommend()` call — `_rank` calls `affinity_score` once per candidate, which
without caching would mean one BigQuery read per candidate against the
free-tier quota. Small bounded cache, no TTL: a little cross-request staleness
is fine given the daily refresh cadence; eviction just costs an extra query,
never wrong data within a process's lifetime.
"""
from functools import lru_cache

from google.cloud import bigquery

from . import db

_ENGAGED_THRESHOLD = 0.3   # sector interest, normalized to the user's own max, to count as "engaged"
_SYMBOL_WEIGHT = 0.7       # direct interest in the candidate itself...
_SECTOR_WEIGHT = 0.3       # ...outweighs merely having browsed its sector


@lru_cache(maxsize=32)
def _load(user_id: str) -> tuple[tuple[str, str, float], ...]:
    """(kind, key, interest) rows for one user. A tuple, not a dict — lru_cache
    only requires the *arguments* to be hashable, but a mutable dict return
    value would let one caller's edits leak into every other caller sharing
    this cached result."""
    rows = db.query_rows(
        f"""SELECT kind, key, interest FROM {db.current_view('behaviour_summary')}
            WHERE user_id = @u""",
        [bigquery.ScalarQueryParameter("u", "STRING", user_id)])
    return tuple((r["kind"], r["key"], r["interest"]) for r in rows)


def engaged_sectors(user_id: str) -> list[str]:
    """Sectors the user has shown meaningful interest in — feeds #93's
    candidate-sector generation."""
    return [key for kind, key, interest in _load(user_id)
            if kind == "sector" and interest >= _ENGAGED_THRESHOLD]


def affinity_score(user_id: str, symbol: str, sector: str | None = None) -> float:
    """A bounded interest tilt for `symbol`, in [0, 1]."""
    summary = {(kind, key): interest for kind, key, interest in _load(user_id)}
    sym_interest = summary.get(("symbol", symbol), 0.0)
    sec_interest = summary.get(("sector", sector), 0.0) if sector else 0.0
    return min(1.0, _SYMBOL_WEIGHT * sym_interest + _SECTOR_WEIGHT * sec_interest)
