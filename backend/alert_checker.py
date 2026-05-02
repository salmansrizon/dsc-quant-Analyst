"""
Checks price alerts against latest market data and triggers notifications.
"""
from utils.bigquery_helper import BigQueryHelper
import pandas as pd
from datetime import datetime, timezone

def check_alerts():
    bq = BigQueryHelper()
    
    # 1. Fetch active alerts
    alerts_table = bq._get_full_table_id("price_alerts")
    sql_alerts = f"SELECT * FROM `{alerts_table}` WHERE is_triggered = false"
    alerts = bq.client.query(sql_alerts).to_dataframe()
    
    if alerts.empty:
        print("No active alerts to check.")
        return

    # 2. Fetch latest prices from datamatrix
    dm_table = bq._get_full_table_id("lankabd_datamatrix")
    sql_prices = f"SELECT Symbol, LTP FROM `{dm_table}`"
    prices = bq.client.query(sql_prices).to_dataframe()
    
    # Merge alerts with current prices
    df = alerts.merge(prices, on='Symbol', how='left')
    df['LTP'] = pd.to_numeric(df['LTP'], errors='coerce')
    
    triggered_ids = []
    
    for _, row in df.iterrows():
        if pd.isna(row['LTP']):
            continue
            
        target = float(row['target_price'])
        ltp = float(row['LTP'])
        triggered = False
        
        if row['direction'] == 'above' and ltp >= target:
            triggered = True
        elif row['direction'] == 'below' and ltp <= target:
            triggered = True
            
        if triggered:
            triggered_ids.append(row['id'])
            print(f"ALERT TRIGGERED: {row['Symbol']} hit {ltp} (Target: {target} {row['direction']})")

    # 3. Mark alerts as triggered in BigQuery
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
        
        # TODO: Here we would call the notification service to send Telegram/WhatsApp messages
        return triggered_ids
    
    return []

if __name__ == "__main__":
    check_alerts()
