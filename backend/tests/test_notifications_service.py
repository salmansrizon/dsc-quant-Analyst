"""The delivery log + log-before-send lock (ticket #66, from #34).

`begin` claims a delivery by appending a `sending` row and refuses to start a
second for a crossing that already has one — that refusal is the duplicate
lock. `resolve` records the outcome. No BigQuery: db.query_rows / append_version
/ find_current are stubbed.
"""
import pytest

from backend import notifications_service as ns


@pytest.fixture
def store(monkeypatch):
    """Capture appends; control what the dup-lock query returns."""
    state = {"appends": [], "open": []}

    monkeypatch.setattr(ns.db, "append_version",
                        lambda table, rows: state["appends"].extend(rows))
    monkeypatch.setattr(ns.db, "query_rows", lambda sql, params=None: state["open"])
    return state


def test_begin_appends_a_sending_row_and_returns_its_id(store):
    nid = ns.begin(user_id="u1", alert_id="a1", channel="email",
                   type_="price_alert", subject="GP above 100")
    assert nid is not None
    assert len(store["appends"]) == 1
    row = store["appends"][0]
    assert row["status"] == ns.SENDING
    assert row["id"] == nid
    assert row["alert_id"] == "a1"


def test_begin_refuses_when_a_delivery_is_already_open(store):
    store["open"] = [{"id": "existing"}]  # a sending/sent row exists
    nid = ns.begin(user_id="u1", alert_id="a1", channel="email",
                   type_="price_alert", subject="dup")
    assert nid is None
    assert store["appends"] == [], "the lock must not append a second sending row"


def test_transactional_email_is_never_deduplicated(store):
    # alert_id=None (a password reset): each is its own event, so the dup-lock
    # query is skipped and a row is always appended.
    store["open"] = [{"id": "existing"}]  # would block an alert, but not this
    nid = ns.begin(user_id="u1", alert_id=None, channel="email",
                   type_="password_reset", subject="Reset your password")
    assert nid is not None
    assert len(store["appends"]) == 1


def test_resolve_appends_the_resolved_status(store, monkeypatch):
    current = {"id": "n1", "user_id": "u1", "alert_id": "a1", "channel": "email",
               "type": "price_alert", "subject": "s", "status": ns.SENDING,
               "attempts": 1, "error": None}
    monkeypatch.setattr(ns.db, "find_current", lambda table, **m: current)

    ns.resolve("n1", ns.SENT)
    assert store["appends"][-1]["status"] == ns.SENT
    assert store["appends"][-1]["id"] == "n1"


def test_resolve_records_the_error_on_failure(store, monkeypatch):
    current = {"id": "n1", "status": ns.SENDING, "error": None}
    monkeypatch.setattr(ns.db, "find_current", lambda table, **m: current)

    ns.resolve("n1", ns.FAILED, error="smtp 550")
    assert store["appends"][-1]["status"] == ns.FAILED
    assert store["appends"][-1]["error"] == "smtp 550"


def test_resolve_is_a_noop_for_an_unknown_id(store, monkeypatch):
    monkeypatch.setattr(ns.db, "find_current", lambda table, **m: None)
    ns.resolve("ghost", ns.SENT)
    assert store["appends"] == []
