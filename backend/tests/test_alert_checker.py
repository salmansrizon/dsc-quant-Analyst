"""Tests for the alert-checker batch job (ticket #48).

The job had three defects and no tests at all:
  1. It merged pandas frames on 'Symbol' while the alerts table stores 'symbol',
     so it raised KeyError before firing a single alert. The join now happens in
     SQL (alerts_service.pending_alerts), so the mismatch cannot recur.
  2. It built its UPDATE by string interpolation — the only mutation bypassing
     db. DML is now a 403 anyway on the free tier (#52).
  3. It committed is_triggered=true and THEN reached a `# TODO: notification`
     comment, consuming every alert it ever fired without telling anyone.
"""
import pytest

from backend import alert_checker


def _alert(**over):
    base = {
        "id": "a1", "user_id": "u1", "symbol": "GP",
        "target_price": 100.0, "direction": "above", "current_price": 150.0,
    }
    base.update(over)
    return base


# ── is_met ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("direction, target, price, expected", [
    ("above", 100.0, 150.0, True),
    ("above", 100.0, 100.0, True),    # at the target counts
    ("above", 100.0, 99.9, False),
    ("below", 100.0, 50.0, True),
    ("below", 100.0, 100.0, True),
    ("below", 100.0, 100.1, False),
])
def test_is_met_compares_against_the_target(direction, target, price, expected):
    assert alert_checker.is_met(
        _alert(direction=direction, target_price=target, current_price=price)
    ) is expected


def test_is_met_is_false_when_the_symbol_has_no_price():
    # The LEFT JOIN yields NULL for a symbol absent from the datamatrix.
    assert alert_checker.is_met(_alert(current_price=None)) is False


def test_is_met_is_false_on_an_unparsable_price():
    assert alert_checker.is_met(_alert(current_price="n/a")) is False


def test_is_met_is_false_on_an_unknown_direction():
    assert alert_checker.is_met(_alert(direction="sideways")) is False


def test_is_met_tolerates_a_null_direction():
    assert alert_checker.is_met(_alert(direction=None)) is False


def test_is_met_accepts_numeric_strings():
    assert alert_checker.is_met(_alert(target_price="100", current_price="150")) is True


# ── check_alerts ─────────────────────────────────────────────────────────────

@pytest.fixture
def pending(monkeypatch):
    """Control what pending_alerts returns; record any mark_triggered call."""
    state = {"alerts": [], "marked": []}

    def _mark(ids):
        state["marked"].extend(ids)
        return len(ids)

    monkeypatch.setattr(alert_checker.alerts_service, "pending_alerts",
                        lambda: state["alerts"])
    monkeypatch.setattr(alert_checker.alerts_service, "mark_triggered", _mark)
    return state


def test_no_pending_alerts_is_a_noop(pending):
    assert alert_checker.check_alerts() == {"delivered": [], "undelivered": []}
    assert pending["marked"] == []


def test_alerts_that_do_not_meet_their_condition_are_left_alone(pending):
    pending["alerts"] = [_alert(current_price=50.0)]  # target 100, direction above
    assert alert_checker.check_alerts() == {"delivered": [], "undelivered": []}
    assert pending["marked"] == []


def test_without_a_notifier_a_met_alert_is_reported_but_not_consumed(pending):
    """The heart of defect 3: marking is what consumes the alert."""
    pending["alerts"] = [_alert()]

    result = alert_checker.check_alerts()

    assert [a["id"] for a in result["undelivered"]] == ["a1"]
    assert result["delivered"] == []
    assert pending["marked"] == [], "an undelivered alert must stay pending (#34)"


def test_a_delivered_alert_is_marked_triggered(pending):
    pending["alerts"] = [_alert()]
    result = alert_checker.check_alerts(notifier=lambda a: True)
    assert [a["id"] for a in result["delivered"]] == ["a1"]
    assert result["undelivered"] == []
    assert pending["marked"] == ["a1"]


def test_a_declined_alert_stays_pending(pending):
    pending["alerts"] = [_alert()]
    result = alert_checker.check_alerts(notifier=lambda a: False)
    assert result["delivered"] == []
    assert [a["id"] for a in result["undelivered"]] == ["a1"]
    assert pending["marked"] == []


def test_a_notifier_that_raises_does_not_consume_the_alert(pending):
    def boom(alert):
        raise RuntimeError("telegram is down")

    pending["alerts"] = [_alert()]
    result = alert_checker.check_alerts(notifier=boom)
    assert result["delivered"] == []
    assert [a["id"] for a in result["undelivered"]] == ["a1"]
    assert pending["marked"] == [], "a delivery failure must not consume the alert"


def test_one_failed_delivery_does_not_block_the_others(pending):
    pending["alerts"] = [_alert(id="a1"), _alert(id="a2"), _alert(id="a3")]

    def flaky(alert):
        if alert["id"] == "a2":
            raise RuntimeError("nope")
        return True

    result = alert_checker.check_alerts(notifier=flaky)
    assert [a["id"] for a in result["delivered"]] == ["a1", "a3"]
    assert [a["id"] for a in result["undelivered"]] == ["a2"]
    assert pending["marked"] == ["a1", "a3"]  # a2 remains pending for the next run


def test_only_the_alerts_that_are_met_get_delivered(pending):
    pending["alerts"] = [
        _alert(id="hit", current_price=150.0),
        _alert(id="miss", current_price=50.0),
        _alert(id="noprice", current_price=None),
    ]
    result = alert_checker.check_alerts(notifier=lambda a: True)
    assert [a["id"] for a in result["delivered"]] == ["hit"]
    assert pending["marked"] == ["hit"]


# ── main / exit code ─────────────────────────────────────────────────────────

def test_main_exits_zero_when_nothing_is_met(pending):
    pending["alerts"] = [_alert(current_price=50.0)]
    assert alert_checker.main() == 0


def test_main_exits_non_zero_when_an_alert_is_met_but_undeliverable(pending):
    # A scheduler reads the exit code. "Alerts are firing and nobody is being
    # told" is not a healthy run, and stays true until #34 lands.
    pending["alerts"] = [_alert()]
    assert alert_checker.main() == 1

