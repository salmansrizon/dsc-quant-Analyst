"""Route tests *through* the API seam (#62 part 3).

Only 6 of the app's routes were ever exercised through TestClient; the rest were
tested by importing the service module directly — past the seam production
crosses (the `payload: dict` handling, the auth dependency, HTTP status codes).
And the auth fixture needed real BigQuery, so anything wanting a logged-in
caller inherited that — which is how test_admin_exports sat inert while signup
was broken for months (#51).

This drives the HTTP layer offline: `dependency_overrides` swaps the auth
dependency for a fake user, and `db._client` / `db.append_version` are stubbed —
the same in-memory adapters the mutation tests already use. Two adapters
(BigQuery in prod, fakes here) justify the seam.
"""
import pytest
from fastapi.testclient import TestClient

from backend.api import app
from backend.auth import get_current_user
from backend.models import UserResponse
from backend import db
from backend.tests.fakes import FakeClient, AppendLog, rows as fake_rows

FAKE_USER = UserResponse(id="u1", email="u1@example.com", phone="", full_name="",
                         role="user", created_at=None)


@pytest.fixture
def authed():
    """A TestClient whose auth dependency is overridden to a fixed user — no
    token, no BigQuery, just the fake caller every protected route receives."""
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_a_protected_route_without_auth_is_rejected():
    # No override: the real HTTPBearer dependency runs and refuses.
    client = TestClient(app)
    resp = client.get("/api/alerts")
    assert resp.status_code in (401, 403)


def test_get_alerts_returns_the_callers_alerts(authed, monkeypatch):
    monkeypatch.setattr(db, "_client", FakeClient(result_rows=fake_rows(
        {"id": "a1", "symbol": "GP", "condition_json": '{"op":"above","value":250}',
         "is_active": True, "created_at": "2026-01-01", "current_price": 257.0},
    )))
    resp = authed.get("/api/alerts")
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["symbol"] == "GP"
    assert body[0]["target_price"] == 250      # reconstructed from condition_json
    assert body[0]["direction"] == "above"


def test_get_watchlist_through_the_seam(authed, monkeypatch):
    monkeypatch.setattr(db, "_client", FakeClient(result_rows=fake_rows(
        {"id": "w1", "symbol": "GP", "added_at": "2026-01-01",
         "LTP": 257.0, "ChangePct": 1.2, "Sector": "Telecom"},
    )))
    resp = authed.get("/api/watchlist")
    assert resp.status_code == 200
    assert resp.json()[0]["symbol"] == "GP"


def test_post_portfolio_rejects_a_zero_buy_price(authed):
    # The #62 part-2 guard, asserted at the HTTP seam: pydantic rejects it with
    # 422 before the handler (and the division-by-zero query) is ever reached.
    resp = authed.post("/api/portfolio",
                       json={"symbol": "GP", "buy_price": 0, "quantity": 10})
    assert resp.status_code == 422


def test_post_alert_creates_through_the_seam(authed, monkeypatch):
    # _current_price reads (FakeClient); the create appends (AppendLog).
    monkeypatch.setattr(db, "_client", FakeClient(result_rows=fake_rows({"price": 257.0})))
    log = AppendLog()
    monkeypatch.setattr(db, "append_version", log)

    resp = authed.post("/api/alerts",
                       json={"symbol": "gp", "target_price": 250, "direction": "above"})
    assert resp.status_code == 200
    assert resp.json()["symbol"] == "GP"           # upper-cased by the service
    assert log.appends[0]["table"] == "alerts"
    assert log.appends[0]["rows"][0]["condition_json"] == '{"op": "above", "value": 250.0}'


def test_post_alert_rejects_a_bad_direction(authed):
    # AlertCreate.direction is pattern-constrained — the seam rejects it as 422.
    resp = authed.post("/api/alerts",
                       json={"symbol": "GP", "target_price": 250, "direction": "sideways"})
    assert resp.status_code == 422


# ── bootstrap-admin (#81, ported from main, secured) ─────────────────────────

def test_bootstrap_admin_disabled_without_a_configured_secret(monkeypatch):
    monkeypatch.delenv("ADMIN_BOOTSTRAP_SECRET", raising=False)
    resp = TestClient(app).post("/api/admin/bootstrap-admin",
                                json={"email": "x@y.com", "secret": "anything"})
    assert resp.status_code == 500  # fail-hard, never open (main's default-secret vuln)


def test_bootstrap_admin_rejects_a_wrong_secret(monkeypatch):
    monkeypatch.setenv("ADMIN_BOOTSTRAP_SECRET", "real")
    resp = TestClient(app).post("/api/admin/bootstrap-admin",
                                json={"email": "x@y.com", "secret": "wrong"})
    assert resp.status_code == 403


def test_bootstrap_admin_promotes_with_the_right_secret(monkeypatch):
    monkeypatch.setenv("ADMIN_BOOTSTRAP_SECRET", "real")
    import backend.api as api
    promoted = {}
    monkeypatch.setattr(api, "get_user_by_email",
                        lambda e: UserResponse(id="u9", email=e, phone="", full_name="",
                                               role="user", created_at=None))
    monkeypatch.setattr(api, "update_user", lambda uid, fields: promoted.update(fields) or True)
    resp = TestClient(app).post("/api/admin/bootstrap-admin",
                                json={"email": "x@y.com", "secret": "real"})
    assert resp.status_code == 200
    assert promoted == {"role": "admin"}


# ── Investor profile (#85, spine #84) ────────────────────────────────────────

def test_get_profile_me_returns_neutral_default_when_unset(authed, monkeypatch):
    monkeypatch.setattr(db, "_client", FakeClient(result_rows=[]))
    resp = authed.get("/api/profile/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_default"] is True
    assert (body["goal"], body["risk"], body["horizon"]) == ("growth", "med", "medium")


def test_put_profile_me_saves_and_returns_resolved(authed, monkeypatch):
    from backend import profile_service
    monkeypatch.setattr(profile_service, "list_sector_names", lambda: ["Bank", "Pharma"])
    monkeypatch.setattr(db, "append_version", AppendLog())
    # get_profile readback after save:
    monkeypatch.setattr(db, "_client", FakeClient(result_rows=fake_rows(
        {"id": "u1", "user_id": "u1", "goal": "income", "risk": "low",
         "horizon": "long", "sector_prefs": '["Bank"]', "is_default": False})))
    resp = authed.put("/api/profile/me", json={
        "goal": "income", "risk": "low", "horizon": "long", "sector_prefs": ["Bank"]})
    assert resp.status_code == 200
    assert resp.json()["sector_prefs"] == ["Bank"]
    assert resp.json()["is_default"] is False


def test_put_profile_me_rejects_unknown_sector(authed, monkeypatch):
    from backend import profile_service
    monkeypatch.setattr(profile_service, "list_sector_names", lambda: ["Bank"])
    resp = authed.put("/api/profile/me", json={
        "goal": "growth", "risk": "med", "horizon": "medium", "sector_prefs": ["Nope"]})
    assert resp.status_code == 400


def test_put_profile_me_rejects_bad_enum(authed):
    resp = authed.put("/api/profile/me", json={
        "goal": "gambling", "risk": "med", "horizon": "medium", "sector_prefs": []})
    assert resp.status_code == 422


def test_profile_routes_require_auth():
    client = TestClient(app)
    assert client.get("/api/profile/me").status_code in (401, 403)


# ── Fit engine (#88, spine #84) ──────────────────────────────────────────────

def test_get_fit_scores_a_symbol_through_the_seam(authed, monkeypatch):
    def dispatch(sql, params=None):
        if "investor_profiles" in sql:
            return []                              # neutral default profile
        if "SELECT Sector FROM" in sql:
            return [{"Sector": "Telecom"}]
        if "Symbol, Sector, LTP" in sql:
            return [{"Symbol": "GP", "Sector": "Telecom", "LTP": 300.0},
                    {"Symbol": "ROBI", "Sector": "Telecom", "LTP": 30.0}]
        if "price_archive" in sql:
            return [{"Symbol": "GP", "pe": 10.0, "vol": 0.05, "bars": 30},
                    {"Symbol": "ROBI", "pe": 20.0, "vol": 0.2, "bars": 30}]
        if "fundamentals_earnings" in sql:
            return [{"symbol": "GP", "year": 2018, "eps": 5.0, "nav": 40.0},
                    {"symbol": "GP", "year": 2024, "eps": 12.0, "nav": 60.0}]
        if "fundamentals_dividends" in sql:
            return [{"symbol": "GP", "year": 2024, "dividend_type": "ANNUAL",
                     "cash_dividend_pct": 200.0, "publish_date": "2024-06-01"}]
        return []
    monkeypatch.setattr(db, "query_rows", dispatch)

    resp = authed.get("/api/fit/gp")
    assert resp.status_code == 200
    body = resp.json()
    assert body["symbol"] == "GP"
    assert {a["axis"] for a in body["axes"]} == {"Value", "Income", "Growth", "Stability", "Sector"}
    assert body["disclaimer"]


def test_fit_route_requires_auth():
    assert TestClient(app).get("/api/fit/GP").status_code in (401, 403)


def test_post_fit_batch_scores_multiple_symbols_through_the_seam(authed, monkeypatch):
    # #89: the batched seam a page with many visible rows calls instead of
    # fanning out one GET /api/fit/{symbol} per row — the sector cohort must
    # still only be built once, same as score_many's own contract.
    def dispatch(sql, params=None):
        if "investor_profiles" in sql:
            return []                              # neutral default profile
        if "SELECT Sector FROM" in sql:
            return [{"Sector": "Telecom"}]
        if "Symbol, Sector, LTP" in sql:
            return [{"Symbol": "GP", "Sector": "Telecom", "LTP": 300.0},
                    {"Symbol": "ROBI", "Sector": "Telecom", "LTP": 30.0}]
        if "price_archive" in sql:
            return [{"Symbol": "GP", "pe": 10.0, "vol": 0.05, "bars": 30},
                    {"Symbol": "ROBI", "pe": 20.0, "vol": 0.2, "bars": 30}]
        if "fundamentals_earnings" in sql:
            return [{"symbol": "GP", "year": 2018, "eps": 5.0, "nav": 40.0},
                    {"symbol": "GP", "year": 2024, "eps": 12.0, "nav": 60.0}]
        if "fundamentals_dividends" in sql:
            return [{"symbol": "GP", "year": 2024, "dividend_type": "ANNUAL",
                     "cash_dividend_pct": 200.0, "publish_date": "2024-06-01"}]
        return []
    monkeypatch.setattr(db, "query_rows", dispatch)

    resp = authed.post("/api/fit/batch", json={"symbols": ["gp", "robi"]})
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"GP", "ROBI"}
    assert body["GP"]["symbol"] == "GP"
    assert {a["axis"] for a in body["GP"]["axes"]} == {"Value", "Income", "Growth", "Stability", "Sector"}


def test_fit_batch_route_requires_auth():
    resp = TestClient(app).post("/api/fit/batch", json={"symbols": ["GP"]})
    assert resp.status_code in (401, 403)


def test_fit_batch_route_rejects_an_empty_symbol_list(authed):
    resp = authed.post("/api/fit/batch", json={"symbols": []})
    assert resp.status_code == 422


def test_portfolio_health_route(authed, monkeypatch):
    def dispatch(sql, params=None):
        if "p.symbol" in sql:                              # get_portfolio
            return [{"symbol": "GP", "current_price": 300.0, "quantity": 10}]
        if "investor_profiles" in sql:
            return []                                      # neutral default profile
        if "UNNEST" in sql:                                # _sectors_for
            return [{"Symbol": "GP", "Sector": "Bank"}]
        return []                                          # cohort reads -> empty
    monkeypatch.setattr(db, "query_rows", dispatch)

    resp = authed.get("/api/portfolio/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["holdings_valued"] == 1
    assert body["is_default_profile"] is True              # no profile set
    kinds = {f["kind"] for f in body["findings"]}
    assert {"concentration", "count"} <= kinds             # structural findings always
    assert body["disclaimer"]


def test_portfolio_health_route_requires_auth():
    assert TestClient(app).get("/api/portfolio/health").status_code in (401, 403)


def test_recommendations_route(authed, monkeypatch):
    from backend import recommendation_service
    monkeypatch.setattr(recommendation_service, "recommend", lambda uid: {
        "recs": [], "nudges": [{"kind": "set_profile", "headline": "h",
                                "reason": "r", "symbols": []}],
        "is_default_profile": True, "disclaimer": "d"})
    resp = authed.get("/api/recommendations")
    assert resp.status_code == 200
    assert resp.json()["nudges"][0]["kind"] == "set_profile"


def test_recommendations_route_requires_auth():
    assert TestClient(app).get("/api/recommendations").status_code in (401, 403)


def test_feed_route(authed, monkeypatch):
    from backend import feed_service
    monkeypatch.setattr(feed_service, "feed", lambda uid, limit=20, offset=0: {
        "items": [{"kind": "nudge", "headline": "h", "reason": "r",
                   "symbol": None, "symbols": [], "sources": []}],
        "next_offset": None, "is_default_profile": True, "disclaimer": "d"})
    resp = authed.get("/api/feed")
    assert resp.status_code == 200
    assert resp.json()["items"][0]["kind"] == "nudge"


def test_feed_route_requires_auth():
    assert TestClient(app).get("/api/feed").status_code in (401, 403)


# ── Behaviour capture (#86, spine #84) ───────────────────────────────────────

def test_post_behaviour_appends_a_batch(authed, monkeypatch):
    from backend import behaviour_service
    captured = {}
    monkeypatch.setattr(behaviour_service, "record_events",
                        lambda uid, events: captured.update(uid=uid, events=events) or len(events))
    resp = authed.post("/api/behaviour", json={"events": [
        {"event_type": "view", "symbol": "GP"},
        {"event_type": "sector_view", "sector": "Bank"}]})
    assert resp.status_code == 202
    assert resp.json()["recorded"] == 2
    assert captured["uid"] == "u1"


def test_post_behaviour_rejects_a_bad_event_type(authed):
    resp = authed.post("/api/behaviour", json={"events": [{"event_type": "hovered"}]})
    assert resp.status_code == 422                       # not in the Literal set


def test_watchlist_add_emits_a_behaviour_event(authed, monkeypatch):
    from backend import behaviour_service, watchlist_service
    monkeypatch.setattr(watchlist_service, "add_to_watchlist", lambda uid, sym: {"status": "added"})
    emitted = []
    monkeypatch.setattr(behaviour_service, "record_events",
                        lambda uid, events: emitted.extend(events) or len(events))
    resp = authed.post("/api/watchlist", json={"symbol": "GP"})
    assert resp.status_code == 200
    assert emitted[0]["event_type"] == "watchlist_add"


def test_behaviour_route_requires_auth():
    assert TestClient(app).post("/api/behaviour", json={"events": []}).status_code in (401, 403)
