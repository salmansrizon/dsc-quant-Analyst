"""Investor profile: contract loader + append-only save (#85, spine #84)."""
import json

import pytest

from backend import db, profile_service as ps
from backend.models import InvestorProfile
from backend.tests.fakes import AppendLog, FakeClient, rows as fake_rows


@pytest.fixture
def appended(monkeypatch):
    log = AppendLog()
    monkeypatch.setattr(db, "append_version", log)
    return log


# ── get_profile: the contract #88 consumes ──────────────────────────────────

def test_absent_profile_resolves_to_neutral_default(monkeypatch):
    monkeypatch.setattr(db, "_client", FakeClient(result_rows=[]))
    p = ps.get_profile("nobody")
    assert isinstance(p, InvestorProfile)
    assert (p.goal, p.risk, p.horizon) == ("growth", "med", "medium")
    assert p.sector_prefs == []
    assert p.is_default is True


def test_present_profile_parses_sector_prefs_to_a_ranked_list(monkeypatch):
    monkeypatch.setattr(db, "_client", FakeClient(result_rows=fake_rows(
        {"id": "u1", "user_id": "u1", "goal": "income", "risk": "low",
         "horizon": "long", "sector_prefs": '["Bank","Pharma"]',
         "is_default": False})))
    p = ps.get_profile("u1")
    assert p.goal == "income"
    assert p.sector_prefs == ["Bank", "Pharma"]   # rank order preserved, [0]=top
    assert p.is_default is False


def test_get_profile_never_returns_none_even_on_bad_json(monkeypatch):
    monkeypatch.setattr(db, "_client", FakeClient(result_rows=fake_rows(
        {"id": "u1", "user_id": "u1", "goal": "growth", "risk": "high",
         "horizon": "short", "sector_prefs": "not-json", "is_default": False})))
    p = ps.get_profile("u1")
    assert p.sector_prefs == []                    # bad JSON degrades, not crash


# ── save_profile: append-only upsert keyed by user_id ───────────────────────

def test_save_appends_a_version_keyed_by_user(appended, monkeypatch):
    monkeypatch.setattr(db, "_client", FakeClient(result_rows=fake_rows(
        {"id": "u1", "user_id": "u1", "goal": "income", "risk": "low",
         "horizon": "long", "sector_prefs": '["Bank"]', "is_default": False})))
    ps.save_profile("u1", {"goal": "income", "risk": "low", "horizon": "long",
                           "sector_prefs": ["Bank"]})
    row = appended.appends[0]["rows"][0]
    assert appended.appends[0]["table"] == "investor_profiles"
    assert row["id"] == "u1"                        # upsert key = user_id
    assert row["sector_prefs"] == '["Bank"]'        # stored as JSON string
    assert row["is_default"] is False               # a user-set profile is never default


def test_save_returns_the_resolved_profile(appended, monkeypatch):
    monkeypatch.setattr(db, "_client", FakeClient(result_rows=fake_rows(
        {"id": "u1", "user_id": "u1", "goal": "income", "risk": "low",
         "horizon": "long", "sector_prefs": '["Bank"]', "is_default": False})))
    p = ps.save_profile("u1", {"goal": "income", "risk": "low", "horizon": "long",
                               "sector_prefs": ["Bank"]})
    assert isinstance(p, InvestorProfile)
    assert p.sector_prefs == ["Bank"]


# ── sector universe (feeds the multi-select + save validation) ──────────────

def test_list_sector_names_returns_distinct_names(monkeypatch):
    monkeypatch.setattr(db, "_client", FakeClient(result_rows=fake_rows(
        {"Sector": "Bank"}, {"Sector": "Pharma"})))
    assert ps.list_sector_names() == ["Bank", "Pharma"]
