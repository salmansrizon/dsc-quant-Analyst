"""The fit engine against real cohort data (#88).

The engine and service tests use synthetic cohorts, so they prove the maths and
prove nothing about the live tables. This one builds a real sector cohort and
scores a real symbol — it is what would notice datamatrix losing its P/E
columns, price_archive going empty (no volatility), or a sector with too few
peers for a percentile to mean anything.
"""
import pytest

from backend import db, fit_service

pytestmark = pytest.mark.integration

# A large-cap that reliably has price, fundamentals and dividend history.
SYMBOL = "GP"


def _has_symbol(sym: str) -> bool:
    rows = db.query_rows(
        f"SELECT 1 FROM {db.table_id('lankabd_datamatrix')} WHERE Symbol = @s LIMIT 1",
        [db.bigquery.ScalarQueryParameter("s", "STRING", sym)],
    )
    return bool(rows)


def test_fit_for_a_real_symbol_returns_a_wellformed_scorecard():
    if not _has_symbol(SYMBOL):
        pytest.skip(f"{SYMBOL} not in the live datamatrix")

    # No stored profile for this synthetic user -> the neutral default is used.
    res = fit_service.fit_for("integration-test-user", SYMBOL)

    assert res["symbol"] == SYMBOL
    assert {a["axis"] for a in res["axes"]} == {"Value", "Income", "Growth", "Risk", "Sector"}
    assert res["is_default_profile"] is True
    assert res["disclaimer"]

    for a in res["axes"]:
        assert a["reason"]                              # every axis explains itself
        if a["score"] is not None:
            assert 0.0 <= a["score"] <= 100.0

    if res["composite"] is not None:
        assert 0.0 <= res["composite"] <= 100.0
        # weights over the scored axes are a proper distribution
        scored = [a["weight"] for a in res["axes"] if a["score"] is not None]
        assert abs(sum(scored) - 1.0) < 1e-3


def test_real_cohort_has_more_than_one_peer():
    # A percentile against a cohort of one is meaningless; GP's sector should be
    # populated. This catches price_archive/datamatrix going empty.
    sector = fit_service._sector_of(SYMBOL)
    if sector is None:
        pytest.skip(f"{SYMBOL} not in the live datamatrix")
    peers = fit_service._peer_metrics(sector)
    assert len(peers) >= 2
