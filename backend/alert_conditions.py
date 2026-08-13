"""Pure alert-condition logic — no BigQuery, no I/O (ticket #66, from #34).

The type-discriminated core of the alert system: an alert carries a `type` and a
`condition_json`, and this module answers two questions about it — *is the
condition met at the current price* and *is this a crossing worth firing*. Both
are pure functions over plain values, so they are the test surface for the whole
edge-trigger design; the BigQuery-facing code (alerts_service, alert_checker)
leans on them and stays thin.

**Edge-trigger, not level (the #34 decision).** An alert fires on the *crossing*
— the moment its condition goes from unmet to met — not on the condition merely
*being* met. That is what dissolves #48's accumulation: a crossing is by
definition a fresh event, so there is no backlog of "still met" alerts to expire.
The state that makes a crossing detectable is one boolean per alert, `last_met`.

Phase 1 implements only `type="price"`. Adding a type is a new branch in
`is_met` plus its own `condition_json` shape — never a schema migration, because
every type shares the one `condition_json` string column.
"""
import json
from typing import Optional

PRICE = "price"


def parse_condition(condition_json: Optional[str]) -> dict:
    """The stored condition string as a dict. Empty/invalid JSON reads as {}.

    A malformed condition must not crash a sweep over every user's alerts, so
    this fails soft to {}, which `is_met` then reports as unevaluable (None).
    """
    if not condition_json:
        return {}
    try:
        parsed = json.loads(condition_json)
    except (ValueError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def price_condition(op: str, value: float) -> str:
    """Serialize a price condition to the stored `condition_json` shape."""
    return json.dumps({"op": op, "value": value})


def is_met(alert_type: str, condition_json: Optional[str],
           current_price: Optional[float]) -> Optional[bool]:
    """Whether the condition holds at `current_price`.

    Tri-state on purpose (mirrors valuation.sign_is_inverted):

    - True / False — the condition was evaluated and holds / does not hold.
    - None — it *cannot* be evaluated: no price for the symbol, an unknown or
      not-yet-implemented type, or a malformed condition. None is not False;
      a caller must not treat "we couldn't tell" as "not met" and fire a
      down-crossing off it.
    """
    if current_price is None:
        return None
    try:
        price = float(current_price)
    except (TypeError, ValueError):
        return None

    if alert_type != PRICE:
        # Declared-but-not-yet-built types (Phase 2) and genuinely unknown types
        # are both unevaluable here — deliberately, so the sweep skips them
        # rather than guessing.
        return None

    cond = parse_condition(condition_json)
    op = (cond.get("op") or "").lower()
    target = cond.get("value")
    if target is None:
        return None
    try:
        target = float(target)
    except (TypeError, ValueError):
        return None

    if op == "above":
        return price >= target
    if op == "below":
        return price <= target
    return None  # unknown operator — unevaluable, not "not met"


def is_crossing(last_met: Optional[bool], met: Optional[bool]) -> bool:
    """Whether this observation is a fire-worthy up-crossing (unmet -> met).

    Fires only on False -> True. A None `met` (unevaluable this sweep) is never
    a crossing — we cannot claim a transition we could not observe. A True
    `last_met` with a True `met` is the "still met" case edge-triggering exists
    to *not* fire on.
    """
    if met is not True:
        return False
    return last_met is not True
