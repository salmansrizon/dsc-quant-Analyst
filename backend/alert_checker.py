"""Checks price alerts against the latest market data (ticket #48).

    python -m backend.alert_checker          # from the repo root
    python alert_checker.py                  # from backend/

**This does not notify anyone yet.** Marking an alert triggered is what consumes
it — the user never sees it again — so an alert is only marked once a notifier
has accepted it. There is no notification channel (that decision is #34), so by
default nothing is marked and matched alerts stay pending: they will fire when
the channel lands, rather than being silently consumed now.

That is the opposite of what this file used to do. It committed
`is_triggered = true` and *then* reached a `# TODO: notification` comment, so
every alert it ever fired was marked handled and never delivered.
"""
import logging
import os
import sys
from typing import Callable, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import alerts_service  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# A notifier takes an alert and returns whether it was delivered. Nothing
# implements this yet — see #34.
Notifier = Callable[[dict], bool]


def is_met(alert: dict) -> bool:
    """Whether the alert's condition holds at the current price."""
    price = alert.get("current_price")
    target = alert.get("target_price")
    if price is None or target is None:
        return False  # no price for that symbol — cannot say

    try:
        price = float(price)
        target = float(target)
    except (TypeError, ValueError):
        return False

    direction = (alert.get("direction") or "").lower()
    if direction == "above":
        return price >= target
    if direction == "below":
        return price <= target
    logger.warning("Alert %s has an unknown direction %r — skipping.",
                   alert.get("id"), alert.get("direction"))
    return False


def check_alerts(notifier: Optional[Notifier] = None) -> list[dict]:
    """Find alerts whose condition is met. Returns them.

    With a notifier, each delivered alert is marked triggered. Without one,
    nothing is marked — see the module docstring.
    """
    pending = alerts_service.pending_alerts()
    if not pending:
        logger.info("No pending alerts to check.")
        return []

    met = [a for a in pending if is_met(a)]
    for a in met:
        logger.info("ALERT MET: %s at %s (target: %s %s)",
                    a["symbol"], a["current_price"], a["target_price"], a["direction"])

    if not met:
        logger.info("Checked %d pending alert(s); none met their condition.", len(pending))
        return []

    if notifier is None:
        logger.warning(
            "%d alert(s) met their condition but there is no notification channel "
            "(#34). Leaving them pending — marking them now would consume them "
            "without telling anyone.", len(met),
        )
        return met

    delivered = []
    for alert in met:
        try:
            if notifier(alert):
                delivered.append(alert)
            else:
                logger.warning("Notifier declined alert %s — leaving it pending.", alert["id"])
        except Exception:
            # A delivery failure must not consume the alert.
            logger.exception("Notifier raised for alert %s — leaving it pending.", alert["id"])

    if delivered:
        marked = alerts_service.mark_triggered([a["id"] for a in delivered])
        logger.info("Delivered and marked %d alert(s) triggered.", marked)
    return delivered


def main() -> int:
    check_alerts()
    return 0


if __name__ == "__main__":
    sys.exit(main())
