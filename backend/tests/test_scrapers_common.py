"""Tests for the shared scraper plumbing (ticket #47).

These ~35 lines were byte-identical across three scrapers and tested by none of
them. get_symbol_universe replaces four copies of a symbol lookup, two of which
built `WHERE Sector = '{sector}'` by interpolation.
"""
import logging
import pathlib
import subprocess
import sys

import pytest

from backend import db
from backend.scrapers import common
from backend.tests.fakes import FakeClient, rows as fake_rows

BACKEND = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture
def scrapers(monkeypatch):
    """The three scrapers, imported the way they actually run (cwd=backend)."""
    monkeypatch.syspath_prepend(str(BACKEND))
    import dataGrid
    import priceArchive
    import announcement
    return dataGrid, priceArchive, announcement


def test_no_scraper_carries_its_own_copy_of_the_shared_plumbing(scrapers):
    """Equality, not identity.

    The scrapers import `scrapers.common` with cwd=backend while this test
    imports `backend.scrapers.common` — one file, two module objects, so `is`
    can never hold here. That split is the drift #56 tracks. Equality still
    catches what matters: a re-added local copy that has diverged.
    """
    dataGrid, priceArchive, announcement = scrapers

    for mod in scrapers:
        assert mod.HEADERS == common.HEADERS, f"{mod.__name__} has drifted from common.HEADERS"

    # The functions must be the shared ones, not re-declared locally.
    for mod in scrapers:
        assert mod.get_session.__module__.endswith("scrapers.common")
    for mod in (priceArchive, announcement):
        assert mod.get_symbol_universe.__module__.endswith("scrapers.common")
        assert mod.get_date_range.__module__.endswith("scrapers.common")


def test_get_session_retries_the_failures_worth_retrying():
    retry = common.get_session().get_adapter("https://lankabd.com").max_retries
    assert retry.total == 3
    assert retry.backoff_factor == 1
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

    common.get_symbol_universe(sector="Bank")
    call = client.calls[0]
    assert "Sector = @sector" in call["sql"]
    assert call["params"] == {"sector": "Bank"}
    assert "Bank" not in call["sql"]


def test_get_symbol_universe_returns_empty_on_failure(monkeypatch):
    class _Boom:
        def query(self, *a, **k):
            raise RuntimeError("BigQuery is down")

    monkeypatch.setattr(db, "_client", _Boom())
    # Every caller treats an empty universe as fatal and logs its own message.
    assert common.get_symbol_universe() == []


# ── The caller's logger must be used, or the diagnostics vanish ──────────────

class _RecordingLog:
    def __init__(self):
        self.infos, self.errors = [], []

    def info(self, msg):
        self.infos.append(msg)

    def error(self, msg):
        self.errors.append(msg)


def test_the_callers_logger_receives_the_symbol_count(monkeypatch):
    # common's own logger has no handlers, so its INFO never emits and its
    # ERROR misses the run's logfile. The scrapers pass their utils.logger.Log.
    monkeypatch.setattr(db, "_client", FakeClient(result_rows=fake_rows({"Symbol": "GP"})))
    log = _RecordingLog()

    common.get_symbol_universe(logger=log)

    assert any("Found 1 symbols" in m for m in log.infos)


def test_the_callers_logger_receives_the_failure(monkeypatch):
    class _Boom:
        def query(self, *a, **k):
            raise RuntimeError("BigQuery is down")

    monkeypatch.setattr(db, "_client", _Boom())
    log = _RecordingLog()

    assert common.get_symbol_universe(logger=log) == []
    # The one line that explains why a scrape found zero symbols.
    assert any("Error fetching symbols" in m for m in log.errors)


def test_the_scrapers_pass_their_own_logger(scrapers):
    import inspect
    _, priceArchive, announcement = scrapers
    for mod in (priceArchive, announcement):
        source = inspect.getsource(mod)
        assert "get_symbol_universe(logger=logger)" in source or \
               "get_symbol_universe(sector=sector, logger=logger)" in source


# ── The standalone import path, as bigquery_helper's test does it ────────────

def test_scrapers_import_common_with_cwd_backend():
    """pytest puts the repo root on sys.path, so `from backend import db`
    always wins here and common's `except ImportError` branch is never taken.
    A subprocess is the only way to exercise how the scrapers actually run.
    """
    script = (
        "from scrapers.common import HEADERS, get_session, get_symbol_universe\n"
        "from scrapers import common\n"
        "assert common.HEADERS is HEADERS\n"
        "print('ok', len(HEADERS))\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", script], cwd=BACKEND, capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.startswith("ok")
