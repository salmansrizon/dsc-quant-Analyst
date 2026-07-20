"""Behaviour roll-up (#86, spine #84): turn the 7-day raw event window into a
per-user interest summary.

`compute_summary` is pure — events + current holdings/watchlist + a clock in,
`behaviour_summary` rows out — so the weighting and decay test against fixtures.
`rollup()` is the daily ETL entry: it reads each active user's window and appends
new summary versions (append-only, no DML).

Signals (decision Q5): per-event-type weights, a 7-day half-life recency decay,
watchlist_remove dampens (floored at 0), and current portfolio/watchlist holdings
add a standing signal. Interest is normalized 0..1 per user per kind.
"""
from collections import defaultdict
from datetime import datetime, timezone

from . import db

HALF_LIFE_DAYS = 7.0
_WEIGHTS = {
    "view": 1.0, "sector_view": 1.0, "watchlist_add": 3.0,
    "watchlist_remove": -2.0, "portfolio": 4.0, "screener_run": 0.5,
}
# Current membership counts as a standing signal on top of event history.
_STANDING = {"portfolio": 4.0, "watchlist": 3.0}


def _decay(age_days: float) -> float:
    return 0.5 ** (age_days / HALF_LIFE_DAYS)


def _as_dt(v) -> datetime:
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(str(v)).replace(tzinfo=timezone.utc)


def compute_summary(user_id: str, events: list[dict], holdings: list[str],
                    watchlist: list[str], now: datetime) -> list[dict]:
    """behaviour_summary rows for one user. events: [{event_type, symbol, sector,
    created_at}]. holdings/watchlist: currently-held symbols (standing signal)."""
    raw: dict[tuple[str, str], float] = defaultdict(float)
    count: dict[tuple[str, str], int] = defaultdict(int)
    last: dict[tuple[str, str], datetime] = {}

    def touch(kind, key, weighted, when):
        if not key:
            return
        raw[(kind, key)] += weighted
        count[(kind, key)] += 1
        prev = last.get((kind, key))
        if prev is None or when > prev:
            last[(kind, key)] = when

    for e in events:
        w = _WEIGHTS.get(e["event_type"])
        if w is None:
            continue
        when = _as_dt(e["created_at"])
        weighted = w * _decay(max((now - when).total_seconds() / 86400.0, 0.0))
        # A stock view carrying its sector feeds both the symbol and the sector.
        touch("symbol", e.get("symbol"), weighted, when)
        touch("sector", e.get("sector"), weighted, when)

    # Standing signals from current state — no decay, present membership.
    for sym in holdings:
        raw[("symbol", sym)] += _STANDING["portfolio"]
    for sym in watchlist:
        raw[("symbol", sym)] += _STANDING["watchlist"]

    # Floor at 0 (remove can drive a key negative), then normalize per kind.
    floored = {k: max(v, 0.0) for k, v in raw.items()}
    max_by_kind: dict[str, float] = defaultdict(float)
    for (kind, _key), v in floored.items():
        max_by_kind[kind] = max(max_by_kind[kind], v)

    rows = []
    for (kind, key), v in floored.items():
        top = max_by_kind[kind]
        interest = round(v / top, 4) if top > 0 else 0.0
        when = last.get((kind, key))
        rows.append({
            "id": f"{user_id}|{kind}|{key}",
            "user_id": user_id, "kind": kind, "key": key,
            "interest": interest, "event_count": count.get((kind, key), 0),
            "last_event_at": when,
            "updated_at": now, "is_deleted": False,
        })
    return rows


def _active_users() -> list[str]:
    rows = db.query_rows(
        f"SELECT DISTINCT user_id FROM {db.table_id('behaviour_events')}")
    return [r["user_id"] for r in rows]


def _events_for(user_id: str) -> list[dict]:
    from google.cloud import bigquery
    return db.query_rows(
        f"""SELECT event_type, symbol, sector, created_at
            FROM {db.table_id('behaviour_events')} WHERE user_id = @u""",
        [bigquery.ScalarQueryParameter("u", "STRING", user_id)])


def _symbols(table: str, user_id: str) -> list[str]:
    from google.cloud import bigquery
    rows = db.query_rows(
        f"SELECT DISTINCT symbol FROM {db.current_view(table)} WHERE user_id = @u",
        [bigquery.ScalarQueryParameter("u", "STRING", user_id)])
    return [r["symbol"] for r in rows if r.get("symbol")]


def rollup(now: datetime | None = None) -> int:
    """Recompute every active user's interest summary. Returns rows appended."""
    now = now or datetime.now(timezone.utc)
    total = 0
    for user_id in _active_users():
        rows = compute_summary(
            user_id, _events_for(user_id),
            _symbols("portfolios", user_id), _symbols("watchlists", user_id), now)
        if rows:
            db.append_version("behaviour_summary", rows)
            total += len(rows)
    return total


if __name__ == "__main__":
    n = rollup()
    print(f"behaviour rollup: appended {n} summary rows")
