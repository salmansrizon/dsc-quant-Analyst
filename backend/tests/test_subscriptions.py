"""Subscriptions/bundles/pricing over the append-only layer (#77).

Ported from main, which used UPDATE DML + WRITE_TRUNCATE. These assert the
rewrite: a decision/deactivation is an appended version (db.revise), never a
mutation, and the seed is idempotent.
"""
import pytest

from backend import db, subscriptions_service as subs
from backend.tests.fakes import AppendLog, FakeClient, rows as fake_rows


@pytest.fixture
def appended(monkeypatch):
    log = AppendLog()
    monkeypatch.setattr(db, "append_version", log)
    return log


def test_create_subscription_appends_a_pending_row(appended):
    out = subs.create_subscription("u1", {
        "medium": ["telegram"], "alert_channel": True, "digest_channel": False,
        "alert_cap": 10, "digest_cadence": "daily", "bundle_id": None,
    })
    assert out["status"] == "pending"
    assert appended.appends[0]["table"] == "subscription_packages"
    row = appended.appends[0]["rows"][0]
    assert row["status"] == "pending" and row["user_id"] == "u1"
    assert row["medium"] == ["telegram"]


def test_decide_subscription_appends_a_new_status_version(monkeypatch, appended):
    monkeypatch.setattr(db, "_client", FakeClient(result_rows=fake_rows(
        {"id": "s1", "user_id": "u1", "status": "pending", "is_deleted": False},
    )))
    out = subs.decide_subscription("s1", "admin1", approved=True)
    assert out["status"] == "active"
    row = appended.appends[0]["rows"][0]
    assert row["status"] == "active" and row["decided_by"] == "admin1"
    assert row["user_id"] == "u1"          # carried forward by revise


def test_reject_sets_rejected(monkeypatch, appended):
    monkeypatch.setattr(db, "_client", FakeClient(result_rows=fake_rows(
        {"id": "s1", "status": "pending", "is_deleted": False})))
    assert subs.decide_subscription("s1", "a", approved=False)["status"] == "rejected"


def test_create_bundle_is_active(appended):
    b = subs.create_bundle("admin1", {
        "name": "Pro", "medium": ["email"], "alert_channel": True,
        "digest_channel": True, "alert_cap": 50, "digest_cadence": "weekly", "price": 500,
    })
    assert b["is_active"] is True
    assert appended.appends[0]["rows"][0]["created_by"] == "admin1"


def test_deactivate_bundle_appends_inactive_version(monkeypatch, appended):
    monkeypatch.setattr(db, "_client", FakeClient(result_rows=fake_rows(
        {"id": "b1", "name": "Pro", "is_active": True, "price": 500.0, "is_deleted": False})))
    subs.deactivate_bundle("b1")
    row = appended.appends[0]["rows"][0]
    assert row["is_active"] is False and row["name"] == "Pro"   # rest carried forward


def test_seed_pricing_weights_is_idempotent(monkeypatch, appended):
    # First run: nothing present -> all 6 seeded.
    monkeypatch.setattr(db, "_client", FakeClient(result_rows=[]))
    assert subs.seed_pricing_weights() == 6
    assert appended.appends[0]["rows"][0]["id"] == "medium|telegram"

    # Second run: all present -> none appended.
    appended.appends.clear()
    monkeypatch.setattr(db, "_client", FakeClient(result_rows=fake_rows(
        *[{"id": f"{d}|{k}"} for d, k, _ in subs._PRICING_SEED])))
    assert subs.seed_pricing_weights() == 0
    assert appended.appends == []
