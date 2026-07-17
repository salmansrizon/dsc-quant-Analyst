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

    def __init__(self):
        self.uploads = []

    def upload_dataframe(self, df, table, truncate=False):
        self.uploads.append({"table": table, "rows": len(df), "truncate": truncate})


@pytest.fixture(autouse=True)
def spy(monkeypatch, tmp_path):
    helper = _SpyHelper()
    monkeypatch.chdir(tmp_path)  # the CSV lands here, not in the repo
    monkeypatch.setattr(dataGrid, "BigQueryHelper", lambda: helper)
    monkeypatch.setattr(dataGrid.time, "sleep", lambda *_: None)
    return helper


def test_partial_scrape_refuses_to_replace_the_universe(monkeypatch, tmp_path, spy):
    monkeypatch.setattr(dataGrid, "get_available_sectors", lambda: ["Banks", "Textile", "Pharma"])
    # Textile fails; the other two succeed. The old code would have truncated
    # the whole table down to two sectors' symbols.
    monkeypatch.setattr(
        dataGrid, "scrape_lankabd",
        lambda sector=None: None if sector == "Textile" else _frame(sector),
    )

    with pytest.raises(dataGrid.PartialScrapeError) as exc:
        dataGrid.scrape_all_sectors()

    assert exc.value.failed_sectors == ["Textile"]
    assert exc.value.total_sectors == 3
    assert spy.uploads == [], "a partial scrape must not reach BigQuery"
    # The scraped work is still preserved locally.
    assert (tmp_path / "lankabd_data_all_sectors.csv").exists()


def test_complete_scrape_replaces_the_universe(monkeypatch, spy):
    monkeypatch.setattr(dataGrid, "get_available_sectors", lambda: ["Banks", "Textile"])
    monkeypatch.setattr(dataGrid, "scrape_lankabd", lambda sector=None: _frame(sector))

    result = dataGrid.scrape_all_sectors()

    assert len(result) == 2
    assert spy.uploads == [
        {"table": "lankabd_datamatrix", "rows": 2, "truncate": True}
    ]


def test_a_known_empty_sector_is_not_a_failure(monkeypatch, spy):
    # Debenture and G-SEC (T.Bond) carry no listings on every run (23 sectors
    # offered, 21 with rows), so their emptiness is expected, not a failure.
    monkeypatch.setattr(dataGrid, "get_available_sectors", lambda: ["Banks", "Debenture"])
    monkeypatch.setattr(
        dataGrid, "scrape_lankabd",
        lambda sector=None: pd.DataFrame() if sector == "Debenture" else _frame(sector),
    )

    result = dataGrid.scrape_all_sectors()

    assert len(result) == 1  # only Banks contributed rows
    assert spy.uploads == [
        {"table": "lankabd_datamatrix", "rows": 1, "truncate": True}
    ]


def test_an_unexpectedly_empty_sector_blocks_the_upload(monkeypatch, spy):
    # scrape_lankabd fetches ONE page and filters it client-side, so an empty
    # frame only means no row carried this label — a truncated page or a renamed
    # sector is indistinguishable from a real empty. Only the known-empty
    # sectors get the benefit of the doubt; Banks coming back empty is a
    # partial scrape and must not land.
    monkeypatch.setattr(dataGrid, "get_available_sectors", lambda: ["Banks", "Textile"])
    monkeypatch.setattr(
        dataGrid, "scrape_lankabd",
        lambda sector=None: pd.DataFrame() if sector == "Banks" else _frame(sector),
    )

    with pytest.raises(dataGrid.PartialScrapeError) as exc:
        dataGrid.scrape_all_sectors()
    assert exc.value.failed_sectors == ["Banks"]
    assert spy.uploads == []


def test_a_broken_sector_scrape_blocks_the_upload(monkeypatch, spy):
    # None means the scrape broke — that sector's symbols are unknown.
    monkeypatch.setattr(dataGrid, "get_available_sectors", lambda: ["Banks", "Textile"])
    monkeypatch.setattr(
        dataGrid, "scrape_lankabd",
        lambda sector=None: None if sector == "Textile" else _frame(sector),
    )

    with pytest.raises(dataGrid.PartialScrapeError):
        dataGrid.scrape_all_sectors()
    assert spy.uploads == []


def test_a_broken_known_empty_sector_is_still_a_failure(monkeypatch, spy):
    # Expected-empty buys leniency for an empty frame, not for a failed scrape.
    monkeypatch.setattr(dataGrid, "get_available_sectors", lambda: ["Banks", "Debenture"])
    monkeypatch.setattr(
        dataGrid, "scrape_lankabd",
        lambda sector=None: None if sector == "Debenture" else _frame(sector),
    )

    with pytest.raises(dataGrid.PartialScrapeError) as exc:
        dataGrid.scrape_all_sectors()
    assert exc.value.failed_sectors == ["Debenture"]
    assert spy.uploads == []


def test_total_failure_returns_none_without_uploading(monkeypatch, spy):
    monkeypatch.setattr(dataGrid, "get_available_sectors", lambda: ["Banks"])
    monkeypatch.setattr(dataGrid, "scrape_lankabd", lambda sector=None: None)

    assert dataGrid.scrape_all_sectors() is None
    assert spy.uploads == []


def test_no_sectors_found_returns_none_without_uploading(monkeypatch, spy):
    monkeypatch.setattr(dataGrid, "get_available_sectors", lambda: [])

    assert dataGrid.scrape_all_sectors() is None
    assert spy.uploads == []


def test_main_exits_non_zero_on_a_partial_scrape(monkeypatch, spy):
    # A scheduler reads the exit code, not the log — a refused scrape must not
    # look like a successful refresh.
    monkeypatch.setattr(dataGrid, "get_available_sectors", lambda: ["Banks", "Textile"])
    monkeypatch.setattr(
        dataGrid, "scrape_lankabd",
        lambda sector=None: None if sector == "Textile" else _frame(sector),
    )
    assert dataGrid.main() == 1
    assert spy.uploads == []


def test_main_exits_non_zero_when_every_sector_fails(monkeypatch, spy):
    # scrape_all_sectors returns None here rather than raising — main() must
    # still not report success.
    monkeypatch.setattr(dataGrid, "get_available_sectors", lambda: ["Banks"])
    monkeypatch.setattr(dataGrid, "scrape_lankabd", lambda sector=None: None)
    assert dataGrid.main() == 1
    assert spy.uploads == []


def test_main_exits_non_zero_when_no_sectors_are_listed(monkeypatch, spy):
    monkeypatch.setattr(dataGrid, "get_available_sectors", lambda: [])
    assert dataGrid.main() == 1


def test_main_exits_zero_on_a_complete_scrape(monkeypatch, spy):
    monkeypatch.setattr(dataGrid, "get_available_sectors", lambda: ["Banks"])
    monkeypatch.setattr(dataGrid, "scrape_lankabd", lambda sector=None: _frame(sector))
    assert dataGrid.main() == 0
    assert len(spy.uploads) == 1


def _page(headers, rows):
    """Minimal DataMatrix page scrape_lankabd knows how to parse."""
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows
    )
    return f"<html><table id='TableDataMatrix'><thead>{head}</thead><tbody>{body}</tbody></table></html>"


class _FakeResponse:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


def _session_serving(html):
    class _S:
        def get(self, *a, **k):
            return _FakeResponse(html)
    return _S()


def test_missing_sector_column_fails_instead_of_returning_everything(monkeypatch):
    """A page without a Sector column must not hand back the whole table.

    scrape_lankabd filters client-side, so returning the unfiltered frame gave
    every sector a copy of the entire table — N copies concatenated, no failure
    signalled, and the universe replaced with an N-way duplicate.
    """
    html = _page(["Symbol", "LTP"], [["GP", "1.0"], ["BEXIMCO", "2.0"]])
    monkeypatch.setattr(dataGrid, "get_session", lambda: _session_serving(html))

    assert dataGrid.scrape_lankabd(sector="Banks") is None


def test_sector_filter_returns_only_that_sectors_rows(monkeypatch):
    html = _page(
        ["Symbol", "Sector", "LTP"],
        [["GP", "Banks", "1.0"], ["SQUARE", "Pharma", "2.0"]],
    )
    monkeypatch.setattr(dataGrid, "get_session", lambda: _session_serving(html))

    df = dataGrid.scrape_lankabd(sector="Banks")
    assert list(df["Symbol"]) == ["GP"]
