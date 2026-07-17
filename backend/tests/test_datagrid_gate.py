"""dataGrid must not replace the symbol universe with a partial scrape (#45).

lankabd_datamatrix is a full-replace target and the symbol universe for
everything downstream. Before this gate, `if all_data:` let a run where 1 of N
sectors succeeded overwrite the whole table.

dataGrid is a standalone script (`python dataGrid.py`, cwd=backend), so it is
imported here the way it actually runs rather than as a package module.
"""
import sys
import pathlib

import pandas as pd
import pytest

BACKEND = pathlib.Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import dataGrid  # noqa: E402


def _frame(symbol):
    return pd.DataFrame([{"Symbol": symbol, "Sector": "Banks", "LTP": 1.0}])


class _SpyHelper:
    """Records uploads so a test can prove none happened."""
    uploads = []

    def __init__(self):
        pass

    def upload_dataframe(self, df, table, truncate=False):
        type(self).uploads.append({"table": table, "rows": len(df), "truncate": truncate})


@pytest.fixture(autouse=True)
def isolate(monkeypatch, tmp_path):
    _SpyHelper.uploads = []
    monkeypatch.chdir(tmp_path)  # the CSV lands here, not in the repo
    monkeypatch.setattr(dataGrid, "BigQueryHelper", _SpyHelper)
    monkeypatch.setattr(dataGrid.time, "sleep", lambda *_: None)
    return _SpyHelper


def test_partial_scrape_refuses_to_replace_the_universe(monkeypatch, tmp_path):
    monkeypatch.setattr(dataGrid, "get_available_sectors", lambda: ["Banks", "Textile", "Pharma"])
    # Textile fails; the other two succeed. The old code would have truncated
    # the whole table down to two sectors' symbols.
    monkeypatch.setattr(
        dataGrid, "scrape_lankabd",
        lambda sector=None: None if sector == "Textile" else _frame(sector),
    )

    with pytest.raises(dataGrid.PartialScrapeError) as exc:
        dataGrid.scrape_all_sectors()

    assert "Textile" in str(exc.value)
    assert _SpyHelper.uploads == [], "a partial scrape must not reach BigQuery"
    # The scraped work is still preserved locally.
    assert (tmp_path / "lankabd_data_all_sectors.csv").exists()


def test_complete_scrape_replaces_the_universe(monkeypatch):
    monkeypatch.setattr(dataGrid, "get_available_sectors", lambda: ["Banks", "Textile"])
    monkeypatch.setattr(dataGrid, "scrape_lankabd", lambda sector=None: _frame(sector))

    result = dataGrid.scrape_all_sectors()

    assert len(result) == 2
    assert _SpyHelper.uploads == [
        {"table": "lankabd_datamatrix", "rows": 2, "truncate": True}
    ]


def test_a_genuinely_empty_sector_is_not_a_failure(monkeypatch):
    # Debenture and G-SEC (T.Bond) are always empty on the live site: 23 sectors
    # listed, 21 with listings. Treating "scraped fine, no rows" as a failure
    # would refuse every real run forever. scrape_lankabd signals a true error
    # with None, and an empty sector with an empty frame.
    monkeypatch.setattr(dataGrid, "get_available_sectors", lambda: ["Banks", "Debenture"])
    monkeypatch.setattr(
        dataGrid, "scrape_lankabd",
        lambda sector=None: pd.DataFrame() if sector == "Debenture" else _frame(sector),
    )

    result = dataGrid.scrape_all_sectors()

    assert len(result) == 1  # only Banks contributed rows
    assert _SpyHelper.uploads == [
        {"table": "lankabd_datamatrix", "rows": 1, "truncate": True}
    ]


def test_a_broken_sector_scrape_still_blocks_the_upload(monkeypatch):
    # None means the scrape broke — that sector's symbols are unknown.
    monkeypatch.setattr(dataGrid, "get_available_sectors", lambda: ["Banks", "Textile"])
    monkeypatch.setattr(
        dataGrid, "scrape_lankabd",
        lambda sector=None: None if sector == "Textile" else _frame(sector),
    )

    with pytest.raises(dataGrid.PartialScrapeError):
        dataGrid.scrape_all_sectors()
    assert _SpyHelper.uploads == []


def test_total_failure_still_returns_none_without_uploading(monkeypatch):
    monkeypatch.setattr(dataGrid, "get_available_sectors", lambda: ["Banks"])
    monkeypatch.setattr(dataGrid, "scrape_lankabd", lambda sector=None: None)

    assert dataGrid.scrape_all_sectors() is None
    assert _SpyHelper.uploads == []


def test_no_sectors_found_returns_none_without_uploading(monkeypatch):
    monkeypatch.setattr(dataGrid, "get_available_sectors", lambda: [])

    assert dataGrid.scrape_all_sectors() is None
    assert _SpyHelper.uploads == []


def test_main_exits_non_zero_on_a_partial_scrape(monkeypatch):
    # A scheduler reads the exit code, not the log — a refused scrape must not
    # look like a successful refresh.
    monkeypatch.setattr(dataGrid, "get_available_sectors", lambda: ["Banks", "Textile"])
    monkeypatch.setattr(
        dataGrid, "scrape_lankabd",
        lambda sector=None: None if sector == "Textile" else _frame(sector),
    )
    assert dataGrid.main() == 1
    assert _SpyHelper.uploads == []


def test_main_exits_zero_on_a_complete_scrape(monkeypatch):
    monkeypatch.setattr(dataGrid, "get_available_sectors", lambda: ["Banks"])
    monkeypatch.setattr(dataGrid, "scrape_lankabd", lambda sector=None: _frame(sector))
    assert dataGrid.main() == 0
    assert len(_SpyHelper.uploads) == 1
