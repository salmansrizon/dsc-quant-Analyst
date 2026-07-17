"""Checks price alerts against the latest market data (ticket #48).

    python -m backend.alert_checker          # from the repo root
    python alert_checker.py                  # from backend/

**This does not notify anyone.** There is no notification channel yet — that
decision is #34. Marking an alert triggered is what consumes it (the user never
sees it again), so an alert is only marked once a notifier accepts it. With no
notifier, nothing is marked and matched alerts stay pending.

**What that costs, plainly.** A met alert now stays pending indefinitely: every
run re-reports it, and the pending set only grows until #34 lands. When a
channel does land it will find every alert matched since today still waiting,
against prices that are long stale — so #34 needs a cutoff rule for old pending
alerts, not just a transport. This trades a silent loss for a visible backlog;
the backlog is the better problem, but it is a real one.

The exit code says so: non-zero while alerts are met and undeliverable, because
"nobody is being told" is not a healthy run.
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


def check_alerts(notifier: Optional[Notifier] = None) -> dict:
    """Find alerts whose condition is met and try to deliver them.

    Returns {"delivered": [...], "undelivered": [...]} — both, explicitly,
    because "what fired" and "who still has not been told" are different
    questions and a single list cannot answer both.

    Only delivered alerts are marked triggered; see the module docstring.
    """
    pending = alerts_service.pending_alerts()
    if not pending:
        logger.info("No pending alerts to check.")
        return {"delivered": [], "undelivered": []}

    met = [a for a in pending if is_met(a)]
    for a in met:
        logger.info("ALERT MET: %s at %s (target: %s %s)",
                    a["symbol"], a["current_price"], a["target_price"], a["direction"])

    if not met:
        logger.info("Checked %d pending alert(s); none met their condition.", len(pending))
        return {"delivered": [], "undelivered": []}

    if notifier is None:
        logger.warning(
            "%d alert(s) met their condition but there is no notification channel "
            "(#34). Leaving them pending — marking them now would consume them "
            "without telling anyone.", len(met),
        )
        return {"delivered": [], "undelivered": met}

    delivered, undelivered = [], []
    for alert in met:
        try:
            if notifier(alert):
                delivered.append(alert)
            else:
                logger.warning("Notifier declined alert %s — leaving it pending.", alert["id"])
                undelivered.append(alert)
        except Exception:
            # A delivery failure must not consume the alert.
            logger.exception("Notifier raised for alert %s — leaving it pending.", alert["id"])
            undelivered.append(alert)

    if delivered:
        marked = alerts_service.mark_triggered([a["id"] for a in delivered])
        logger.info("Delivered and marked %d alert(s) triggered.", marked)
    return {"delivered": delivered, "undelivered": undelivered}


def main() -> int:
    """Entry point. Non-zero when alerts are met but nobody can be told.

    dataGrid.py:main does the same for a refused partial scrape — a scheduler
    reads the exit code, not the log.
    """
    return 1 if check_alerts()["undelivered"] else 0


if __name__ == "__main__":
    sys.exit(main())
