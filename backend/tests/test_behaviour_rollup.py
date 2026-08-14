"""Behaviour roll-up (#86): pure compute_summary over fixtures."""
from datetime import datetime, timedelta, timezone

from backend.behaviour_rollup import compute_summary

NOW = datetime(2026, 7, 20, tzinfo=timezone.utc)


def _ev(event_type, symbol=None, sector=None, age_days=0):
    return {"event_type": event_type, "symbol": symbol, "sector": sector,
            "created_at": NOW - timedelta(days=age_days)}


def _by_key(rows, kind):
    return {r["key"]: r for r in rows if r["kind"] == kind}


def test_top_symbol_normalizes_to_one():
    rows = compute_summary("u1", [
        _ev("view", symbol="GP"), _ev("view", symbol="GP"),
        _ev("view", symbol="ROBI")], [], [], NOW)
    sym = _by_key(rows, "symbol")
    assert sym["GP"]["interest"] == 1.0
    assert 0 < sym["ROBI"]["interest"] < 1.0


def test_recent_events_outweigh_old_ones():
    fresh = compute_summary("u1", [_ev("view", symbol="GP", age_days=0)], [], [], NOW)
    stale = compute_summary("u1", [_ev("view", symbol="GP", age_days=14)], [], [], NOW)
    # both normalize to 1.0 alone; assert the raw decay via event_count-independent
    # comparison: add a fixed competitor so normalization reveals the decay.
    mixed = compute_summary("u1", [
        _ev("view", symbol="GP", age_days=14), _ev("view", symbol="ROBI", age_days=0)],
        [], [], NOW)
    sym = _by_key(mixed, "symbol")
    assert sym["ROBI"]["interest"] == 1.0            # fresh wins
    assert sym["GP"]["interest"] < 0.5               # two half-lives old


def test_watchlist_remove_dampens_and_floors_at_zero():
    rows = compute_summary("u1", [
        _ev("watchlist_add", symbol="GP"), _ev("watchlist_remove", symbol="GP"),
        _ev("watchlist_remove", symbol="GP")], [], [], NOW)
    sym = _by_key(rows, "symbol")
    assert sym["GP"]["interest"] == 0.0              # net negative floored to 0


def test_sector_affinity_from_event_sector():
    rows = compute_summary("u1", [
        _ev("view", symbol="GP", sector="Telecom"),
        _ev("sector_view", sector="Bank")], [], [], NOW)
    sec = _by_key(rows, "sector")
    assert set(sec) == {"Telecom", "Bank"}


def test_standing_holdings_signal_without_events():
    rows = compute_summary("u1", [], ["GP"], [], NOW)
    sym = _by_key(rows, "symbol")
    assert sym["GP"]["interest"] == 1.0              # only signal -> top
    assert sym["GP"]["event_count"] == 0             # standing, not an event


def test_row_id_is_user_kind_key():
    rows = compute_summary("u1", [_ev("view", symbol="GP")], [], [], NOW)
    assert rows[0]["id"] == "u1|symbol|GP"
    assert rows[0]["is_deleted"] is False
