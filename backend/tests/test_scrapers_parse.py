"""Offline parse tests for the price-archive and announcement scrapers (#69).

Neither had a test. The parse (HTML → DataFrame) is embedded in the fetch
functions, so a test stubs the session — feeding crafted HTML — and asserts the
parsed rows, exactly as #45's test_datagrid_gate does. No network.
"""
import pytest

import priceArchive
import announcement


class _Resp:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


class _Session:
    """A fake requests session: canned HTML for get() and post()."""
    def __init__(self, get_html="", post_html=""):
        self._get_html = get_html
        self._post_html = post_html

    def get(self, *a, **k):
        return _Resp(self._get_html)

    def post(self, *a, **k):
        return _Resp(self._post_html)


# ── priceArchive ─────────────────────────────────────────────────────────────

PRICE_TABLE = """
<table class="table">
  <thead><tr>
    <th>Date</th><th>Open</th><th>High</th><th>Low</th><th>Close</th><th>Volume</th>
  </tr></thead>
  <tbody>
    <tr><td>2025/01/02</td><td>10</td><td>12</td><td>9</td><td>11</td><td>1000</td></tr>
    <tr><td>2025/01/03</td><td>11</td><td>13</td><td>10</td><td>12</td><td>2000</td></tr>
  </tbody>
</table>
"""


def test_price_archive_parses_a_table_into_rows(monkeypatch):
    monkeypatch.setattr(priceArchive, "get_session", lambda: _Session(get_html=PRICE_TABLE))
    df = priceArchive.scrape_price_archive("GP", "2025-01-01", "2025-01-05")
    assert df is not None and len(df) == 2
    assert list(df["Close"]) == ["11", "12"]
    assert (df["Symbol"] == "GP").all()      # symbol column stamped
    assert "SMA_20" in df.columns            # schema placeholder present


def test_price_archive_returns_none_on_a_tableless_page(monkeypatch):
    monkeypatch.setattr(priceArchive, "get_session",
                        lambda: _Session(get_html="<html><body>no data</body></html>"))
    assert priceArchive.scrape_price_archive("GP", "2025-01-01", "2025-01-05") is None


# ── announcement ─────────────────────────────────────────────────────────────

INIT_WITH_TOKEN = """
<html><body>
  <input name="__RequestVerificationToken" value="tok123" />
</body></html>
"""

ANNOUNCEMENTS = """
<html><body>
  <div class="list-group-item">
    <a href="/Company/Overview?cid=1">GP</a>
    <span class="small text-dark font-weight-bold">02 Jan, 2025</span>
    <p>Board meeting on dividend.</p>
  </div>
  <div class="list-group-item">
    <a href="https://lankabd.com/x">BEXIMCO</a>
    <span class="small text-dark font-weight-bold">03 Jan, 2025</span>
    <p>EPS declared.</p>
  </div>
</body></html>
"""


def test_announcement_parses_list_group_items(monkeypatch):
    monkeypatch.setattr(announcement, "get_session",
                        lambda: _Session(get_html=INIT_WITH_TOKEN, post_html=ANNOUNCEMENTS))
    df = announcement.scrape_announcement("GP", "2025-01-01", "2025-01-31")
    assert df is not None and len(df) == 2
    assert list(df["Symbol"]) == ["GP", "BEXIMCO"]
    assert list(df["Date"]) == ["2025-01-02", "2025-01-03"]  # '%d %b, %Y' normalized
    assert df.iloc[0]["Link"] == "https://lankabd.com/Company/Overview?cid=1"  # relative → absolute


def test_announcement_raises_on_a_missing_csrf_token(monkeypatch):
    # No token input on the init page: fail loudly (#61) rather than posting
    # token=None and getting an opaque empty 400.
    monkeypatch.setattr(announcement, "get_session",
                        lambda: _Session(get_html="<html></html>", post_html=ANNOUNCEMENTS))
    with pytest.raises(RuntimeError, match="RequestVerificationToken"):
        announcement.scrape_announcement("GP", "2025-01-01", "2025-01-31")
