"""Pure edge-trigger/condition logic (ticket #66). No BigQuery — direct calls.

This is the test surface for the whole alert design: is_met (does the condition
hold) and is_crossing (is this a fire-worthy transition) are pure, so the
BigQuery-facing sweep can stay thin and lean on what is proven here.
"""
import pytest

from backend import alert_conditions as ac


# ── is_met ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("op, value, price, expected", [
    ("above", 100.0, 150.0, True),
    ("above", 100.0, 100.0, True),     # at the target counts
    ("above", 100.0, 99.9, False),
    ("below", 100.0, 50.0, True),
    ("below", 100.0, 100.0, True),
    ("below", 100.0, 100.1, False),
])
def test_is_met_compares_against_the_target(op, value, price, expected):
    cond = ac.price_condition(op, value)
    assert ac.is_met(ac.PRICE, cond, price) is expected


def test_is_met_accepts_numeric_strings():
    assert ac.is_met(ac.PRICE, ac.price_condition("above", 100), "150") is True


def test_is_met_is_none_when_the_symbol_has_no_price():
    # The LEFT JOIN yields NULL for a symbol absent from the datamatrix. None,
    # not False — "we could not tell" must never masquerade as "not met".
    assert ac.is_met(ac.PRICE, ac.price_condition("above", 100), None) is None


def test_is_met_is_none_on_an_unparsable_price():
    assert ac.is_met(ac.PRICE, ac.price_condition("above", 100), "n/a") is None


def test_is_met_is_none_on_an_unknown_operator():
    assert ac.is_met(ac.PRICE, ac.price_condition("sideways", 100), 150.0) is None


def test_is_met_is_none_on_a_malformed_condition():
    assert ac.is_met(ac.PRICE, "not json", 150.0) is None
    assert ac.is_met(ac.PRICE, None, 150.0) is None


def test_is_met_is_none_for_a_not_yet_implemented_type():
    # Phase-2 types are declared but unevaluable here; the sweep must skip them,
    # not guess.
    assert ac.is_met("volume", ac.price_condition("above", 100), 150.0) is None


# ── describe ─────────────────────────────────────────────────────────────────

def test_describe_renders_a_condition_phrase():
    assert ac.describe("GP", ac.price_condition("above", 100.0)) == "GP above 100.0"


def test_describe_tolerates_a_malformed_condition():
    assert ac.describe("GP", "not json") == "GP None None"


# ── is_crossing ──────────────────────────────────────────────────────────────

def test_up_crossing_fires():
    assert ac.is_crossing(last_met=False, met=True) is True


def test_still_met_does_not_fire():
    # The whole point of edge-triggering: being met is not firing.
    assert ac.is_crossing(last_met=True, met=True) is False


def test_down_crossing_does_not_fire():
    assert ac.is_crossing(last_met=True, met=False) is False


def test_unevaluable_is_never_a_crossing():
    assert ac.is_crossing(last_met=False, met=None) is False


def test_baseline_already_met_treated_as_met():
    # An alert created while already met baselines last_met=True, so its first
    # sweep is "still met", not a crossing — it will not fire (#34).
    assert ac.is_crossing(last_met=True, met=True) is False
