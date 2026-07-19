"""Subscriptions, bundles, and pricing (#77, ported from main onto append-only).

main implemented this over `UPDATE` DML (attach/decide) and read-all +
WRITE_TRUNCATE (bundle update/deactivate) — the exact patterns #52/#40 proved
broken on the BigQuery free tier. Here every mutation is a `db.append_version`
or `db.revise`, and reads go through `_current` views. Behaviour (pending ->
approved/rejected lifecycle, à-la-carte vs bundle, pricing lookup) is preserved.
"""
import uuid
from datetime import datetime, timezone

from google.cloud import bigquery

from . import db


def _now():
    return datetime.now(timezone.utc)


# ── Subscriptions ────────────────────────────────────────────────────────────

def create_subscription(user_id: str, data: dict) -> dict:
    sid = str(uuid.uuid4())
    now = _now()
    db.append_version("subscription_packages", [{
        "id": sid, "user_id": user_id,
        "medium": data["medium"],
        "alert_channel": data["alert_channel"], "digest_channel": data["digest_channel"],
        "alert_cap": data["alert_cap"], "digest_cadence": data["digest_cadence"],
        "bundle_id": data.get("bundle_id"),
        "status": "pending",
        "transaction_id": None, "submitted_at": None,
        "decided_at": None, "decided_by": None, "last_digest_sent_at": None,
        "created_at": now, "updated_at": now, "is_deleted": False,
    }])
    return {"id": sid, "status": "pending", "user_id": user_id}


def get_subscription(subscription_id: str) -> dict | None:
    return db.find_current("subscription_packages", id=subscription_id)


def attach_transaction_id(subscription_id: str, transaction_id: str) -> dict:
    db.revise("subscription_packages",
              {"transaction_id": transaction_id, "submitted_at": _now()},
              id=subscription_id)
    return {"id": subscription_id, "transaction_id": transaction_id, "status": "pending"}


def decide_subscription(subscription_id: str, admin_id: str, approved: bool) -> dict:
    status = "active" if approved else "rejected"
    db.revise("subscription_packages",
              {"status": status, "decided_at": _now(), "decided_by": admin_id},
              id=subscription_id)
    return {"id": subscription_id, "status": status}


def list_subscriptions() -> list[dict]:
    return db.query_rows(
        f"SELECT * FROM {db.current_view('subscription_packages')} ORDER BY created_at DESC"
    )


# ── Bundles ──────────────────────────────────────────────────────────────────

def create_bundle(admin_id: str, data: dict) -> dict:
    bid = str(uuid.uuid4())
    now = _now()
    row = {
        "id": bid, "name": data["name"], "medium": data["medium"],
        "alert_channel": data["alert_channel"], "digest_channel": data["digest_channel"],
        "alert_cap": data["alert_cap"], "digest_cadence": data["digest_cadence"],
        "price": data["price"], "is_active": True,
        "created_by": admin_id,
        "created_at": now, "updated_at": now, "is_deleted": False,
    }
    db.append_version("admin_bundles", [row])
    return row


_BUNDLE_FIELDS = ("name", "medium", "alert_channel", "digest_channel",
                  "alert_cap", "digest_cadence", "price")


def update_bundle(bundle_id: str, data: dict) -> dict:
    changes = {k: data[k] for k in _BUNDLE_FIELDS if k in data}
    db.revise("admin_bundles", changes, id=bundle_id)
    return {"id": bundle_id, **changes}


def deactivate_bundle(bundle_id: str) -> dict:
    db.revise("admin_bundles", {"is_active": False}, id=bundle_id)
    return {"id": bundle_id, "is_active": False}


def list_bundles() -> list[dict]:
    return db.query_rows(
        f"SELECT * FROM {db.current_view('admin_bundles')} ORDER BY created_at DESC"
    )


# ── Pricing ──────────────────────────────────────────────────────────────────

def get_pricing() -> dict:
    # `id IS NOT NULL` drops main's pre-append-only INSERTed rows (they predate
    # the id column, so they carry NULL and would double the seeded weights).
    weights = db.query_rows(
        f"SELECT * FROM {db.current_view('pricing_weights')} WHERE id IS NOT NULL")
    bundles = db.query_rows(
        f"SELECT * FROM {db.current_view('admin_bundles')} WHERE COALESCE(is_active, TRUE)"
    )
    return {"weights": weights, "bundles": bundles}


# Static seed for the pricing estimator — main used an INSERT (DML, forbidden);
# here it is an idempotent append keyed by dimension|key.
_PRICING_SEED = [
    ("medium", "telegram", 50.0), ("medium", "whatsapp", 50.0),
    ("medium", "email", 50.0), ("medium", "web_push", 50.0),
    ("channel", "alert", 100.0), ("channel", "digest", 50.0),
]


def seed_pricing_weights() -> int:
    """Idempotent seed: append the placeholder weights not already present."""
    existing = {r["id"] for r in db.query_rows(
        f"SELECT id FROM {db.current_view('pricing_weights')}")}
    now = _now()
    rows = [
        {"id": f"{dim}|{key}", "dimension": dim, "key": key, "weight_price": price,
         "updated_at": now, "is_deleted": False}
        for dim, key, price in _PRICING_SEED
        if f"{dim}|{key}" not in existing
    ]
    if rows:
        db.append_version("pricing_weights", rows)
    return len(rows)


if __name__ == "__main__":
    print("seeded", seed_pricing_weights(), "pricing weights")
