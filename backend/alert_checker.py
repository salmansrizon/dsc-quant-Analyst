"""Edge-trigger alert sweep (ticket #66, reworked from #48/#34).

    python -m backend.alert_checker          # from the repo root

Run as a module, not a bare script: its dependencies import package-relative
(#56), so `python alert_checker.py` from backend/ cannot resolve them.

**Edge-trigger (the #34 decision).** An alert fires on the *crossing* — the
sweep it goes from unmet to met — not on merely being met. Each alert's
`last_met` records where it was; a fire happens only on a False->True flip, and
`last_met` is written back only when it actually flips. This is what dissolves
#48's old accumulation problem: there is no growing backlog of "still met"
alerts to expire, because a crossing is by definition a fresh event.

**One-shot.** A fired alert is marked inactive (`is_active=False`) and does not
re-arm in Phase 1. A down-crossing (met->unmet) just rebaselines `last_met`.

**Delivery is the notifier's job**, injected as a seam so the pure crossing
logic here never imports the email provider. An undelivered crossing is *not*
recorded as fired, so the next sweep retries it — a delivery failure never
consumes an alert (the #48 guarantee, kept).

**Where it runs, and the scale-out (#34 dec.6).** The sweep is triggered by
Vercel Cron hitting POST /api/internal/run-alerts — serverless has no
in-process scheduler. Two ceilings come with that: Vercel Cron on Hobby is
daily / two-crons-max, and a large crossing batch × ~300ms/email can exceed the
function timeout. Both are scale risks, not now risks (single-digit users, ms
sweeps). **The scale-out, when sweep time approaches the function budget:** move
this exact entry point to a standalone GitHub Actions cron (as the ETL scrapers
do, #55) — check_alerts + build_email_notifier run unchanged off a runner with
a 6h budget instead of a function timeout. Nothing here changes; only the
trigger does.
"""
import logging
import sys
from typing import Callable, Optional

# Package-qualified imports (#56): the service modules this pulls in use
# `from . import db` relative imports, so they only resolve when loaded as
# members of the `backend` package — which is why this runs as `python -m
# backend.alert_checker` (or is imported by the API), never as a bare script.
from backend import alerts_service, alert_conditions

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# A notifier takes an alert and returns whether it was delivered.
Notifier = Callable[[dict], bool]


def check_alerts(notifier: Optional[Notifier] = None) -> dict:
    """Sweep active alerts, fire the up-crossings, rebaseline the down-crossings.

    Returns counts, explicitly separating what *fired and was delivered* from
    what crossed but *could not be delivered* — different questions, and a
    single list cannot answer both.
    """
    alerts = alerts_service.active_alerts()
    fired, undelivered, rebaselined = [], [], []

    for alert in alerts:
        met = alert_conditions.is_met(
            alert.get("type"), alert.get("condition_json"), alert.get("current_price"),
        )
        if met is None:
            continue  # no price / unevaluable this sweep — say nothing

        last_met = alert.get("last_met")
        if alert_conditions.is_crossing(last_met, met):
            logger.info("CROSSING: alert %s (%s) met at price %s",
                        alert["id"], alert["symbol"], alert.get("current_price"))
            delivered = _deliver(alert, notifier)
            if delivered:
                alerts_service.record_state(alert, met=True, fired=True)
                fired.append(alert)
            else:
                # Not recorded as fired: last_met stays False, so the next sweep
                # sees the same crossing and retries. A failure never consumes it.
                undelivered.append(alert)
        elif met != bool(last_met):
            # A down-crossing (met->unmet): just rebaseline, no fire.
            alerts_service.record_state(alert, met=met, fired=False)
            rebaselined.append(alert)

    logger.info("Swept %d active alert(s): %d fired, %d undelivered, %d rebaselined.",
                len(alerts), len(fired), len(undelivered), len(rebaselined))
    return {"fired": fired, "undelivered": undelivered, "rebaselined": rebaselined}


def _deliver(alert: dict, notifier: Optional[Notifier]) -> bool:
    """Hand an alert to the notifier; a raise or a None notifier is non-delivery."""
    if notifier is None:
        logger.warning("Alert %s crossed but no notifier is wired — leaving it to retry.",
                       alert["id"])
        return False
    try:
        return bool(notifier(alert))
    except Exception:
        logger.exception("Notifier raised for alert %s — leaving it to retry.", alert["id"])
        return False


def build_email_notifier() -> Notifier:
    """A notifier that emails the alert's owner via Resend, with log-before-send.

    Local imports so the pure sweep above is importable (and testable) without
    pulling in the email provider or the user service.
    """
    from backend import notifications_service, email_sender
    from backend.user_service import get_user_by_id

    def notify(alert: dict) -> bool:
        user = get_user_by_id(alert["user_id"])
        if not user or not user.email:
            logger.warning("Alert %s owner has no email — cannot deliver.", alert["id"])
            return False

        phrase = alert_conditions.describe(alert["symbol"], alert.get("condition_json"))
        subject = f"Alert: {phrase}"
        body = (f"<p>Your alert fired: <b>{phrase}</b> "
                f"(now {alert.get('current_price')}).</p>")

        nid = notifications_service.begin(
            user_id=alert["user_id"], alert_id=alert["id"],
            channel="email", type_="price_alert", subject=subject,
        )
        if nid is None:
            # A sending/sent row already exists for this crossing — already
            # delivered. Treat as delivered so the one-shot is marked fired.
            return True

        try:
            ok = email_sender.send_email(user.email, subject, body)
        except Exception as exc:
            notifications_service.resolve(nid, notifications_service.FAILED, error=str(exc))
            raise
        notifications_service.resolve(
            nid, notifications_service.SENT if ok else notifications_service.FAILED,
        )
        return ok

    return notify


def main() -> int:
    """Entry point. Non-zero when a crossing could not be delivered."""
    result = check_alerts(build_email_notifier())
    return 1 if result["undelivered"] else 0


if __name__ == "__main__":
    sys.exit(main())
