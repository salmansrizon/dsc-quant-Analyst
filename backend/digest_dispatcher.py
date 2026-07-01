"""
Sends portfolio P&L / market digest notifications to subscribers, honoring
each subscription's digest_cadence (daily / alternate / weekly).
"""
from datetime import datetime, timezone

from . import bq_service
from .utils.bigquery_helper import BigQueryHelper
from .notifications.messages import build_digest_message
from .notifications.channels import send_telegram, send_whatsapp, send_web_push

_CADENCE_DAYS = {"alternate": 2, "weekly": 7}


def _is_due(cadence: str, last_sent_at, now) -> bool:
    if cadence == "daily":
        return True
    if last_sent_at is None:
        return True
    days_required = _CADENCE_DAYS[cadence]
    return (now - last_sent_at).days >= days_required


def _deliver_digest(message: str, prefs: dict):
    channels = prefs.get("channels_enabled") or []
    if "telegram" in channels and prefs.get("telegram_chat_id"):
        send_telegram(prefs["telegram_chat_id"], message)
    if "whatsapp" in channels and prefs.get("whatsapp_number"):
        send_whatsapp(prefs["whatsapp_number"], message)
    if "web_push" in channels and prefs.get("web_push_subscription"):
        send_web_push(prefs["web_push_subscription"], {"title": "Daily Market Digest", "body": message})


def dispatch_digests():
    bq = BigQueryHelper()
    now = datetime.now(timezone.utc)

    subs_table = bq._get_full_table_id("subscription_packages")
    sql_subs = f"""
        SELECT id, user_id, digest_cadence, last_digest_sent_at
        FROM `{subs_table}`
        WHERE status = 'active' AND digest_channel = true
    """
    subs = list(bq.client.query(sql_subs).result())

    prefs_table = bq._get_full_table_id("notification_preferences")
    sent_ids = []

    for sub in subs:
        if not _is_due(sub["digest_cadence"], sub["last_digest_sent_at"], now):
            continue

        user_id = sub["user_id"]
        summary = bq_service.portfolio_summary(user_id)
        portfolio_pnl = summary.get("total_pnl") or 0.0
        top_gainers = bq_service.leaderboard("gainer", limit=5)
        top_losers = bq_service.leaderboard("loser", limit=5)
        message = build_digest_message(portfolio_pnl, top_gainers, top_losers)

        try:
            prefs_rows = list(bq.client.query(
                f"SELECT * FROM `{prefs_table}` WHERE user_id = '{user_id}' LIMIT 1"
            ).result())
            prefs = dict(prefs_rows[0]) if prefs_rows else {}
            _deliver_digest(message, prefs)

            sql_update = f"""
            UPDATE `{subs_table}`
            SET last_digest_sent_at = '{now.isoformat()}'
            WHERE id = '{sub["id"]}'
            """
            bq.client.query(sql_update).result()
            sent_ids.append(sub["id"])
        except Exception as e:
            print(f"Digest failed for user {user_id}: {e}")

    return sent_ids


if __name__ == "__main__":
    dispatch_digests()
