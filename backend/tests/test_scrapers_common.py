"""Tests for the shared scraper plumbing (ticket #47).

These ~35 lines were byte-identical across three scrapers and tested by none of
them. get_symbol_universe replaces four copies of a symbol lookup, two of which
built `WHERE Sector = '{sector}'` by string interpolation.
"""
import pytest

from backend import db
from backend.scrapers import common
from backend.tests.fakes import FakeClient, rows as fake_rows


def test_no_scraper_carries_its_own_copy_of_the_shared_plumbing():
    """The three scrapers must take HEADERS and friends from common.

    Equality, not identity: the scrapers run with cwd=backend and import
    `scrapers.common`, while this test imports `backend.scrapers.common` — the
    same file, loaded as two module objects, so `is` can never hold here. That
    split is itself the drift #56 tracks. Equality still catches what matters:
    a re-added local copy that has diverged.
    """
    import sys
    import pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    import dataGrid
    import priceArchive
    import announcement

    for mod in (dataGrid, priceArchive, announcement):
        assert mod.HEADERS == common.HEADERS, f"{mod.__name__} has drifted from common.HEADERS"

    # The functions must be the shared ones, not re-declared locally.
    for mod in (priceArchive, announcement):
        assert mod.get_symbol_universe.__module__.endswith("scrapers.common")
        assert mod.get_date_range.__module__.endswith("scrapers.common")
    for mod in (dataGrid, priceArchive, announcement):
        assert mod.get_session.__module__.endswith("scrapers.common")


def test_the_old_per_scraper_helpers_are_gone():
    import sys
    import pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    import priceArchive
    import announcement

    # get_symbols_from_sectors was byte-identical in both; it is now one
    # parameterized get_symbol_universe.
    for mod in (priceArchive, announcement):
        assert not hasattr(mod, "get_symbols_from_sectors")


def test_get_session_retries_the_failures_worth_retrying():
    session = common.get_session()
    adapter = session.get_adapter("https://lankabd.com")
    retry = adapter.max_retries
    assert retry.total == 3
    assert retry.backoff_factor == 1
    # 429 is in the list because the server is asking us to slow down.
    assert set(retry.status_forcelist) == {429, 500, 502, 503, 504}


def test_get_session_mounts_both_schemes():
    session = common.get_session()
    assert session.get_adapter("http://lankabd.com").max_retries.total == 3
    assert session.get_adapter("https://lankabd.com").max_retries.total == 3


def test_get_date_range_spans_the_requested_years():
    from datetime import datetime

    start, end = common.get_date_range(years=3)
    start_d = datetime.strptime(start, "%Y-%m-%d")
    end_d = datetime.strptime(end, "%Y-%m-%d")
    assert (end_d - start_d).days == 365 * 3


def test_get_date_range_defaults_to_three_years():
    assert common.get_date_range() == common.get_date_range(years=3)


def test_get_symbol_universe_unfiltered(monkeypatch):
    client = FakeClient(result_rows=fake_rows({"Symbol": "GP"}, {"Symbol": "BEXIMCO"}))
    monkeypatch.setattr(db, "_client", client)

    assert common.get_symbol_universe() == ["GP", "BEXIMCO"]
    call = client.calls[0]
    assert "SELECT DISTINCT Symbol" in call["sql"]
    assert "Symbol IS NOT NULL" in call["sql"]
    assert call["params"] == {}


def test_get_symbol_universe_binds_the_sector_rather_than_interpolating(monkeypatch):
    # Two of the four copies this replaces built WHERE Sector = '{sector}'.
    client = FakeClient(result_rows=fake_rows({"Symbol": "GP"}))
    monkeypatch.setattr(db, "_client", client)

    common.get_symbol_universe(sector="Banks")
    call = client.calls[0]
    assert "Sector = @sector" in call["sql"]
    assert call["params"] == {"sector": "Banks"}
    assert "Banks" not in call["sql"]


def test_get_symbol_universe_returns_empty_on_failure(monkeypatch):
    class _Boom:
        def query(self, *a, **k):
            raise RuntimeError("BigQuery is down")

    monkeypatch.setattr(db, "_client", _Boom())
    # Every caller treats an empty universe as fatal and logs its own message.
    assert common.get_symbol_universe() == []
