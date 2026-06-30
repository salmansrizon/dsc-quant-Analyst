"""
Checks price alerts against latest market data and triggers notifications.
"""
from utils.bigquery_helper import BigQueryHelper
import pandas as pd
from datetime import datetime, timezone

from backend.notifications.messages import build_alert_message
from backend.notifications.channels import send_telegram, send_whatsapp, send_web_push


def _deliver_alert(row, ltp: float, prefs: dict):
    symbol = row["Symbol"]
    target = float(row["target_price"])
    direction = row["direction"]
    msg = build_alert_message(symbol=symbol, ltp=ltp, target=target, direction=direction)
    channels = prefs.get("channels_enabled") or []
    if "telegram" in channels and prefs.get("telegram_chat_id"):
        send_telegram(prefs["telegram_chat_id"], msg)
    if "whatsapp" in channels and prefs.get("whatsapp_number"):
        send_whatsapp(prefs["whatsapp_number"], msg)
    if "web_push" in channels and prefs.get("web_push_subscription"):
        send_web_push(prefs["web_push_subscription"], {"title": f"Alert: {symbol}", "body": msg})


def check_alerts():
    bq = BigQueryHelper()

    # 1. Fetch active alerts
    alerts_table = bq._get_full_table_id("price_alerts")
    sql_alerts = f"SELECT * FROM `{alerts_table}` WHERE is_triggered = false"
    alerts = bq.client.query(sql_alerts).to_dataframe()

    if alerts.empty:
        print("No active alerts to check.")
        return []

    # 2. Fetch latest prices from datamatrix
    dm_table = bq._get_full_table_id("lankabd_datamatrix")
    sql_prices = f"SELECT Symbol, LTP FROM `{dm_table}`"
    prices = bq.client.query(sql_prices).to_dataframe()

    df = alerts.merge(prices, on="Symbol", how="left")
    df["LTP"] = pd.to_numeric(df["LTP"], errors="coerce")

    triggered_ids = []
    triggered_rows = []

    for _, row in df.iterrows():
        if pd.isna(row["LTP"]):
            continue
        target = float(row["target_price"])
        ltp = float(row["LTP"])
        triggered = (row["direction"] == "above" and ltp >= target) or \
                    (row["direction"] == "below" and ltp <= target)
        if triggered:
            triggered_ids.append(row["id"])
            triggered_rows.append((row, ltp))
            print(f"ALERT TRIGGERED: {row['Symbol']} hit {ltp} (Target: {target} {row['direction']})")

    # 3. Mark alerts triggered and deliver notifications
    if triggered_ids:
        now = datetime.now(timezone.utc).isoformat()
        ids_str = ", ".join([f"'{i}'" for i in triggered_ids])
        sql_update = f"""
        UPDATE `{alerts_table}`
        SET is_triggered = true, triggered_at = '{now}'
        WHERE id IN ({ids_str})
        """
        bq.client.query(sql_update).result()
        print(f"Updated {len(triggered_ids)} alerts as triggered.")

        prefs_table = bq._get_full_table_id("notification_preferences")
        for row, ltp in triggered_rows:
            user_id = row.get("user_id", "")
            try:
                prefs_rows = list(bq.client.query(
                    f"SELECT * FROM `{prefs_table}` WHERE user_id = '{user_id}' LIMIT 1"
                ).result())
                prefs = dict(prefs_rows[0]) if prefs_rows else {}
                _deliver_alert(row, ltp, prefs)
            except Exception as e:
                print(f"Notification failed for user {user_id}: {e}")

    return triggered_ids


if __name__ == "__main__":
    check_alerts()
