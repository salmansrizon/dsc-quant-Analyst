"""Personalized home feed (#96, spine #84): compose the Dashboard 'for you'
surface.

The personalized content is wholly #93's `recommend()` (recs + strategy nudges);
this service *composes* that stream with non-personalized context — notable
watchlist moves and active alerts — into one ordered, paginated feed (#93's
decision: the feed arranges and paginates, it does not re-rank).

Order: nudges (actionable) → recommendations → watchlist moves → alerts. On-read
Python; no precomputed feed table. Behaviour reason strings ("you viewed 3 pharma
stocks this week") enrich rec items once the affinity formula (#107) lands over
the #86 `user_affinity` summary — omitted, not faked, until then.
"""
from . import watchlist_service, alerts_service
from . import recommendation_service
from .models import Feed, FeedItem
from .fit_engine import DISCLAIMER

# A watchlisted symbol only earns a feed card if it actually moved.
_MOVE_PCT = 3.0


def _rec_items(recos: dict) -> list[FeedItem]:
    items = [FeedItem(kind="nudge", headline=n["headline"], reason=n["reason"],
                      symbols=n.get("symbols", []))
             for n in recos["nudges"]]
    items += [FeedItem(kind="recommendation", headline=f"{r['symbol']} — {r['match']} match",
                       reason=r["reason"], symbol=r["symbol"], sources=r.get("sources", []))
              for r in recos["recs"]]
    return items


def _watchlist_items(user_id: str) -> list[FeedItem]:
    items = []
    for w in watchlist_service.get_watchlist(user_id):
        pct = w.get("ChangePct")
        if pct is None or abs(pct) < _MOVE_PCT:
            continue
        direction = "up" if pct > 0 else "down"
        items.append(FeedItem(
            kind="watchlist_move", symbol=w["symbol"],
            headline=f"{w['symbol']} {direction} {abs(pct):.1f}%",
            reason=f"{w['symbol']} on your watchlist moved {direction} {abs(pct):.1f}% today."))
    return items


def _alert_items(user_id: str) -> list[FeedItem]:
    items = []
    for a in alerts_service.get_alerts(user_id):
        if not a.get("is_active"):
            continue
        items.append(FeedItem(
            kind="alert", symbol=a["symbol"],
            headline=f"Alert active on {a['symbol']}",
            reason=f"Your price alert on {a['symbol']} is active."))
    return items


def feed(user_id: str, limit: int = 20, offset: int = 0) -> dict:
    """The composed 'for you' feed, ordered and paginated."""
    recos = recommendation_service.recommend(user_id)
    items = _rec_items(recos) + _watchlist_items(user_id) + _alert_items(user_id)

    window = items[offset:offset + limit]
    next_offset = offset + limit if offset + limit < len(items) else None
    return Feed(items=window, next_offset=next_offset,
                is_default_profile=recos["is_default_profile"],
                disclaimer=DISCLAIMER).model_dump()
