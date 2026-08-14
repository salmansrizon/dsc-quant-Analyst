"""Behaviour-driven affinity (#107): the affinity_score/engaged_sectors formula
over #86's behaviour_summary, replacing #93's neutral placeholder."""
import pytest

from backend import affinity, db


@pytest.fixture(autouse=True)
def clear_cache():
    # lru_cache persists across tests otherwise — each test gets a clean slate.
    affinity._load.cache_clear()
    yield
    affinity._load.cache_clear()


def _wire(monkeypatch, rows):
    calls = []

    def fake_query_rows(query, params=None):
        calls.append((query, params))
        return rows

    monkeypatch.setattr(db, "query_rows", fake_query_rows)
    return calls


def test_affinity_score_blends_symbol_and_sector_interest_07_03(monkeypatch):
    _wire(monkeypatch, [
        {"kind": "symbol", "key": "GP", "interest": 0.8},
        {"kind": "sector", "key": "Telecom", "interest": 0.4},
    ])
    score = affinity.affinity_score("u1", "GP", "Telecom")
    assert score == pytest.approx(0.7 * 0.8 + 0.3 * 0.4)


def test_affinity_score_caps_at_one(monkeypatch):
    _wire(monkeypatch, [
        {"kind": "symbol", "key": "GP", "interest": 1.0},
        {"kind": "sector", "key": "Telecom", "interest": 1.0},
    ])
    assert affinity.affinity_score("u1", "GP", "Telecom") == 1.0


def test_affinity_score_defaults_to_zero_for_a_cold_start_user(monkeypatch):
    _wire(monkeypatch, [])
    assert affinity.affinity_score("new-user", "GP", "Telecom") == 0.0


def test_affinity_score_skips_the_sector_term_when_sector_is_none(monkeypatch):
    _wire(monkeypatch, [
        {"kind": "symbol", "key": "GP", "interest": 0.5},
        {"kind": "sector", "key": "Telecom", "interest": 1.0},
    ])
    # No sector passed — only the direct-symbol term contributes.
    assert affinity.affinity_score("u1", "GP") == pytest.approx(0.7 * 0.5)


def test_affinity_score_ignores_other_users_and_other_symbols(monkeypatch):
    _wire(monkeypatch, [
        {"kind": "symbol", "key": "ACI", "interest": 0.9},
        {"kind": "sector", "key": "Pharma", "interest": 0.9},
    ])
    assert affinity.affinity_score("u1", "GP", "Telecom") == 0.0


def test_engaged_sectors_includes_at_or_above_threshold(monkeypatch):
    _wire(monkeypatch, [
        {"kind": "sector", "key": "Telecom", "interest": 0.3},
        {"kind": "sector", "key": "Pharma", "interest": 0.29},
        {"kind": "sector", "key": "Bank", "interest": 0.9},
        {"kind": "symbol", "key": "GP", "interest": 1.0},   # a symbol row, not a sector
    ])
    assert set(affinity.engaged_sectors("u1")) == {"Telecom", "Bank"}


def test_engaged_sectors_empty_for_no_behaviour(monkeypatch):
    _wire(monkeypatch, [])
    assert affinity.engaged_sectors("new-user") == []


def test_one_query_serves_engaged_sectors_and_every_affinity_score_call(monkeypatch):
    calls = _wire(monkeypatch, [
        {"kind": "symbol", "key": "GP", "interest": 0.5},
        {"kind": "sector", "key": "Telecom", "interest": 0.5},
    ])
    affinity.engaged_sectors("u1")
    affinity.affinity_score("u1", "GP", "Telecom")
    affinity.affinity_score("u1", "ACI", "Pharma")
    affinity.affinity_score("u1", "SQUARE", "Pharma")
    assert len(calls) == 1


def test_different_users_each_cost_their_own_query(monkeypatch):
    calls = _wire(monkeypatch, [{"kind": "symbol", "key": "GP", "interest": 0.5}])
    affinity.affinity_score("u1", "GP")
    affinity.affinity_score("u2", "GP")
    assert len(calls) == 2
