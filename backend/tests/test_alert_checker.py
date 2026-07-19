"""The edge-trigger alert sweep (ticket #66, reworked from #48).

The sweep fires on the crossing, not on being met; an undelivered crossing is
never recorded as fired, so it retries; a fired alert is one-shot. These tests
drive check_alerts over a controlled set of active alerts and record every
record_state call — no BigQuery.
"""
import pytest

from backend import alert_checker
from backend import alert_conditions as ac


def _alert(**over):
    base = {
        "id": "a1", "user_id": "u1", "type": ac.PRICE, "symbol": "GP",
        "condition_json": ac.price_condition("above", 100.0),
        "last_met": False, "current_price": 150.0,
    }
    base.update(over)
    return base


@pytest.fixture
def sweep(monkeypatch):
    """Control active_alerts; record record_state(alert, met, fired) calls."""
    state = {"alerts": [], "recorded": []}

    def _record(alert, met, fired):
        state["recorded"].append({"id": alert["id"], "met": met, "fired": fired})

    monkeypatch.setattr(alert_checker.alerts_service, "active_alerts",
                        lambda: state["alerts"])
    monkeypatch.setattr(alert_checker.alerts_service, "record_state", _record)
    return state


def test_no_active_alerts_is_a_noop(sweep):
    result = alert_checker.check_alerts(notifier=lambda a: True)
    assert result["fired"] == [] and result["rebaselined"] == []
    assert sweep["recorded"] == []


def test_an_up_crossing_fires_and_is_recorded_fired(sweep):
    sweep["alerts"] = [_alert(last_met=False, current_price=150.0)]  # above 100
    result = alert_checker.check_alerts(notifier=lambda a: True)
    assert [a["id"] for a in result["fired"]] == ["a1"]
    assert sweep["recorded"] == [{"id": "a1", "met": True, "fired": True}]


def test_still_met_does_not_fire_and_records_nothing(sweep):
    # last_met already True: being met is not a crossing.
    sweep["alerts"] = [_alert(last_met=True, current_price=150.0)]
    result = alert_checker.check_alerts(notifier=lambda a: True)
    assert result["fired"] == [] and result["rebaselined"] == []
    assert sweep["recorded"] == []


def test_a_down_crossing_rebaselines_without_firing(sweep):
    # Was met, now below the target: rebaseline last_met=False, no fire.
    sweep["alerts"] = [_alert(last_met=True, current_price=50.0)]
    result = alert_checker.check_alerts(notifier=lambda a: True)
    assert result["fired"] == []
    assert [a["id"] for a in result["rebaselined"]] == ["a1"]
    assert sweep["recorded"] == [{"id": "a1", "met": False, "fired": False}]


def test_an_undelivered_crossing_is_not_recorded_so_it_retries(sweep):
    sweep["alerts"] = [_alert(last_met=False, current_price=150.0)]
    result = alert_checker.check_alerts(notifier=lambda a: False)
    assert [a["id"] for a in result["undelivered"]] == ["a1"]
    assert sweep["recorded"] == [], "a failed delivery must not consume the crossing"


def test_a_notifier_that_raises_does_not_consume_the_crossing(sweep):
    def boom(alert):
        raise RuntimeError("resend is down")

    sweep["alerts"] = [_alert(last_met=False, current_price=150.0)]
    result = alert_checker.check_alerts(notifier=boom)
    assert [a["id"] for a in result["undelivered"]] == ["a1"]
    assert sweep["recorded"] == []


def test_an_unevaluable_alert_is_skipped_entirely(sweep):
    # No price: met is None — neither a crossing nor a rebaseline.
    sweep["alerts"] = [_alert(current_price=None)]
    result = alert_checker.check_alerts(notifier=lambda a: True)
    assert result["fired"] == [] and result["rebaselined"] == []
    assert sweep["recorded"] == []


def test_one_failed_delivery_does_not_block_the_others(sweep):
    sweep["alerts"] = [
        _alert(id="a1", current_price=150.0),
        _alert(id="a2", current_price=150.0),
        _alert(id="a3", current_price=150.0),
    ]

    def flaky(alert):
        return alert["id"] != "a2"

    result = alert_checker.check_alerts(notifier=flaky)
    assert [a["id"] for a in result["fired"]] == ["a1", "a3"]
    assert [a["id"] for a in result["undelivered"]] == ["a2"]
    assert [r["id"] for r in sweep["recorded"]] == ["a1", "a3"]


def test_no_notifier_leaves_crossings_undelivered(sweep):
    sweep["alerts"] = [_alert(last_met=False, current_price=150.0)]
    result = alert_checker.check_alerts()  # no notifier
    assert [a["id"] for a in result["undelivered"]] == ["a1"]
    assert sweep["recorded"] == []


# ── main / exit code ─────────────────────────────────────────────────────────

def test_main_exit_code_reflects_undelivered(sweep, monkeypatch):
    # A scheduler reads the exit code: a crossing nobody was told about is a
    # non-zero run.
    monkeypatch.setattr(alert_checker, "build_notifier", lambda: (lambda a: False))
    sweep["alerts"] = [_alert(last_met=False, current_price=150.0)]
    assert alert_checker.main() == 1

    monkeypatch.setattr(alert_checker, "build_notifier", lambda: (lambda a: True))
    sweep["alerts"] = [_alert(last_met=False, current_price=150.0)]
    assert alert_checker.main() == 0
