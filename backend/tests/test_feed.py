"""Home feed composition (#96). The service's sources (recommend / watchlist /
alerts) are monkeypatched so composition, ordering and pagination test without BQ."""
from backend import feed_service as fs
from backend import recommendation_service, watchlist_service, alerts_service


def _wire(monkeypatch, recos, watchlist, alerts):
    monkeypatch.setattr(recommendation_service, "recommend", lambda uid: recos)
    monkeypatch.setattr(watchlist_service, "get_watchlist", lambda uid: watchlist)
    monkeypatch.setattr(alerts_service, "get_alerts", lambda uid: alerts)


_RECOS = {
    "recs": [{"symbol": "PH1", "match": "strong", "reason": "high yield", "sources": ["fit"]},
             {"symbol": "PH2", "match": "good", "reason": "value", "sources": ["gap"]}],
    "nudges": [{"kind": "unmet_prefs", "headline": "Explore Pharma",
                "reason": "you hold none", "symbols": ["PH1"]}],
    "is_default_profile": False, "disclaimer": "d",
}
_WATCH = [
    {"symbol": "GP", "ChangePct": 5.2, "LTP": 300},     # notable move -> card
    {"symbol": "ROBI", "ChangePct": 0.4, "LTP": 30},    # flat -> no card
    {"symbol": "BEXIM", "ChangePct": None, "LTP": None}, # no price -> no card
]
_ALERTS = [
    {"symbol": "SQUARE", "is_active": True, "current_price": 200},
    {"symbol": "OLD", "is_active": False, "current_price": 10},   # inactive -> skip
]


def test_feed_composes_and_orders_nudge_rec_move_alert(monkeypatch):
    _wire(monkeypatch, _RECOS, _WATCH, _ALERTS)
    out = fs.feed("u1")
    kinds = [i["kind"] for i in out["items"]]
    # nudges first, then recs, then watchlist moves, then alerts
    assert kinds == ["nudge", "recommendation", "recommendation", "watchlist_move", "alert"]
    assert out["is_default_profile"] is False


def test_feed_filters_flat_and_unpriced_watchlist_and_inactive_alerts(monkeypatch):
    _wire(monkeypatch, _RECOS, _WATCH, _ALERTS)
    out = fs.feed("u1")
    moves = [i["symbol"] for i in out["items"] if i["kind"] == "watchlist_move"]
    alerts = [i["symbol"] for i in out["items"] if i["kind"] == "alert"]
    assert moves == ["GP"]                    # ROBI flat, BEXIM unpriced dropped
    assert alerts == ["SQUARE"]               # OLD inactive dropped


def test_feed_paginates_with_next_offset(monkeypatch):
    _wire(monkeypatch, _RECOS, _WATCH, _ALERTS)   # 5 items total
    page = fs.feed("u1", limit=2, offset=0)
    assert len(page["items"]) == 2
    assert page["next_offset"] == 2
    last = fs.feed("u1", limit=2, offset=4)
    assert len(last["items"]) == 1
    assert last["next_offset"] is None


def test_default_profile_feed_still_shows_context_and_set_profile_nudge(monkeypatch):
    recos = {"recs": [], "nudges": [{"kind": "set_profile", "headline": "Set profile",
                                     "reason": "do it", "symbols": []}],
             "is_default_profile": True, "disclaimer": "d"}
    _wire(monkeypatch, recos, _WATCH, _ALERTS)
    out = fs.feed("u1")
    assert out["is_default_profile"] is True
    kinds = [i["kind"] for i in out["items"]]
    assert kinds[0] == "nudge"                        # set-profile prompt leads
    assert "watchlist_move" in kinds and "alert" in kinds   # context still composes
