"""Behaviour capture + roll-up service (#86)."""
from datetime import datetime, timezone

import pytest

from backend import db, behaviour_service, behaviour_rollup


@pytest.fixture
def inserted(monkeypatch):
    log = []
    monkeypatch.setattr(db, "insert_rows", lambda table, rows: log.append((table, rows)))
    return log


def test_record_events_stamps_and_appends_raw_rows(inserted):
    n = behaviour_service.record_events("u1", [
        {"event_type": "view", "symbol": "gp"},
        {"event_type": "screener_run", "payload": {"sector": "Bank"}},
    ])
    assert n == 2
    table, rows = inserted[0]
    assert table == "behaviour_events"
    assert rows[0]["user_id"] == "u1"
    assert rows[0]["symbol"] == "GP"                    # upper-cased server-side
    assert rows[0]["id"] and rows[0]["event_date"]      # server-stamped
    assert rows[1]["payload"] == '{"sector": "Bank"}'   # payload JSON-encoded


def test_record_events_empty_is_a_noop(inserted):
    assert behaviour_service.record_events("u1", []) == 0
    assert inserted == []


def test_emit_records_one_event(inserted):
    behaviour_service.emit("u1", "watchlist_add", symbol="GP")
    _, rows = inserted[0]
    assert rows[0]["event_type"] == "watchlist_add"


def test_rollup_appends_summary_for_active_users(monkeypatch):
    monkeypatch.setattr(behaviour_rollup, "_active_users", lambda: ["u1"])
    monkeypatch.setattr(behaviour_rollup, "_events_for",
                        lambda uid: [{"event_type": "view", "symbol": "GP",
                                      "sector": "Telecom",
                                      "created_at": datetime(2026, 7, 20, tzinfo=timezone.utc)}])
    monkeypatch.setattr(behaviour_rollup, "_symbols", lambda table, uid: [])
    appended = []
    monkeypatch.setattr(db, "append_version", lambda t, rows: appended.append((t, rows)))

    total = behaviour_rollup.rollup(now=datetime(2026, 7, 20, tzinfo=timezone.utc))
    assert total > 0
    table, rows = appended[0]
    assert table == "behaviour_summary"
    assert any(r["kind"] == "symbol" and r["key"] == "GP" for r in rows)
