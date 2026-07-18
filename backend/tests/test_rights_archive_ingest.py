"""Offline parse tests for the rights-archive ingest (#65)."""
import datetime as dt

from scrapers import rights_archive as ra

PAGE = """
<html><body>
<table>
  <thead><tr>
    <th>Symbol</th><th>Right Offer</th><th>Issue Price</th><th>Right Premium</th>
    <th>Record Date</th><th>Year</th>
    <th>Subscription Open Date</th><th>Subscription Close Date</th>
  </tr></thead>
  <tbody>
    <tr><td>AAMRANET</td><td>1R:2</td><td>30</td><td>20</td>
        <td>07-Mar-2024</td><td>2024</td><td>24-Mar-2024</td><td>18-Apr-2024</td></tr>
    <tr><td>alif</td><td>1R: 1</td><td>10</td><td>0</td>
        <td>11-Jan-2018</td><td>-</td><td>-</td><td>-</td></tr>
    <tr><td>NODATE</td><td>1R:1</td><td>10</td><td>0</td>
        <td>-</td><td>-</td><td>-</td><td>-</td></tr>
  </tbody>
</table>
</body></html>
"""


def test_parses_and_normalizes_rows():
    rows = ra.parse_rights(PAGE)
    # NODATE dropped (no record_date), so two remain.
    assert len(rows) == 2
    aamra = rows[0]
    assert aamra["symbol"] == "AAMRANET"
    assert (aamra["offer_new"], aamra["offer_held"]) == (1, 2)
    assert aamra["issue_price"] == 30.0 and aamra["right_premium"] == 20.0
    assert aamra["record_date"] == dt.date(2024, 3, 7)
    assert aamra["year"] == 2024
    assert aamra["id"] == "AAMRANET|2024-03-07"


def test_ratio_tolerates_a_space_and_symbol_is_upcased():
    rows = ra.parse_rights(PAGE)
    alif = rows[1]
    assert alif["symbol"] == "ALIF"                  # lower-case input upcased
    assert (alif["offer_new"], alif["offer_held"]) == (1, 1)  # "1R: 1"
    assert alif["year"] is None                      # '-' -> None
    assert alif["subscription_open"] is None


def test_a_row_without_a_record_date_is_skipped():
    assert all(r["symbol"] != "NODATE" for r in ra.parse_rights(PAGE))


def test_ratio_without_an_r_is_parsed():
    # BERGERPBL uses "1:17" (no R); both forms must parse.
    html = PAGE.replace("1R:2", "1:17")
    rows = ra.parse_rights(html)
    assert (rows[0]["offer_new"], rows[0]["offer_held"]) == (1, 17)


def test_an_unparseable_ratio_is_none_not_a_crash():
    html = PAGE.replace("1R:2", "weird")
    rows = ra.parse_rights(html)
    assert rows[0]["offer_new"] is None and rows[0]["offer_held"] is None
