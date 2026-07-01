from unittest.mock import patch, MagicMock
import pandas as pd
from backend.alert_checker import check_alerts


def _mock_bq(alerts_df, prices_df, caps_rows, prefs_by_user):
    bq = MagicMock()
    bq._get_full_table_id.side_effect = lambda name: name

    def query_side_effect(sql, *args, **kwargs):
        m = MagicMock()
        if "price_alerts" in sql and "is_triggered = false" in sql:
            m.to_dataframe.return_value = alerts_df
        elif "lankabd_datamatrix" in sql:
            m.to_dataframe.return_value = prices_df
        elif "subscription_packages" in sql:
            m.result.return_value = caps_rows
        elif "UPDATE" in sql:
            m.result.return_value = []
        elif "notification_preferences" in sql:
            for uid, prefs in prefs_by_user.items():
                if f"user_id = '{uid}'" in sql:
                    m.result.return_value = [prefs]
                    return m
            m.result.return_value = []
        return m

    bq.client.query.side_effect = query_side_effect
    return bq


def test_alerts_beyond_alert_cap_are_marked_triggered_but_not_delivered():
    alerts_df = pd.DataFrame([
        {"id": "a1", "user_id": "u1", "Symbol": "ACI", "target_price": 100.0, "direction": "above"},
        {"id": "a2", "user_id": "u1", "Symbol": "BRAC", "target_price": 50.0, "direction": "above"},
    ])
    prices_df = pd.DataFrame([
        {"Symbol": "ACI", "LTP": "105.0"},
        {"Symbol": "BRAC", "LTP": "55.0"},
    ])
    caps_rows = [{"user_id": "u1", "alert_cap": 1}]
    prefs_by_user = {"u1": {"channels_enabled": ["telegram"], "telegram_chat_id": "999"}}

    bq = _mock_bq(alerts_df, prices_df, caps_rows, prefs_by_user)

    with patch("backend.alert_checker.BigQueryHelper", return_value=bq), \
         patch("backend.alert_checker.send_telegram") as mock_send:
        triggered_ids = check_alerts()

    assert sorted(triggered_ids) == ["a1", "a2"]
    assert mock_send.call_count == 1


def test_alerts_under_alert_cap_are_all_delivered():
    alerts_df = pd.DataFrame([
        {"id": "a1", "user_id": "u1", "Symbol": "ACI", "target_price": 100.0, "direction": "above"},
        {"id": "a2", "user_id": "u1", "Symbol": "BRAC", "target_price": 50.0, "direction": "above"},
    ])
    prices_df = pd.DataFrame([
        {"Symbol": "ACI", "LTP": "105.0"},
        {"Symbol": "BRAC", "LTP": "55.0"},
    ])
    caps_rows = [{"user_id": "u1", "alert_cap": 5}]
    prefs_by_user = {"u1": {"channels_enabled": ["telegram"], "telegram_chat_id": "999"}}

    bq = _mock_bq(alerts_df, prices_df, caps_rows, prefs_by_user)

    with patch("backend.alert_checker.BigQueryHelper", return_value=bq), \
         patch("backend.alert_checker.send_telegram") as mock_send:
        check_alerts()

    assert mock_send.call_count == 2


def test_alerts_with_no_active_subscription_are_uncapped():
    alerts_df = pd.DataFrame([
        {"id": "a1", "user_id": "u2", "Symbol": "ACI", "target_price": 100.0, "direction": "above"},
        {"id": "a2", "user_id": "u2", "Symbol": "BRAC", "target_price": 50.0, "direction": "above"},
    ])
    prices_df = pd.DataFrame([
        {"Symbol": "ACI", "LTP": "105.0"},
        {"Symbol": "BRAC", "LTP": "55.0"},
    ])
    caps_rows = []  # no active subscription for u2
    prefs_by_user = {"u2": {"channels_enabled": ["telegram"], "telegram_chat_id": "999"}}

    bq = _mock_bq(alerts_df, prices_df, caps_rows, prefs_by_user)

    with patch("backend.alert_checker.BigQueryHelper", return_value=bq), \
         patch("backend.alert_checker.send_telegram") as mock_send:
        check_alerts()

    assert mock_send.call_count == 2
