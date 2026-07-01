from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
from backend.digest_dispatcher import dispatch_digests

NOW = datetime(2026, 7, 1, 9, 0, tzinfo=timezone.utc)


def _mock_bq(subs_rows, prefs_by_user):
    bq = MagicMock()
    bq._get_full_table_id.side_effect = lambda name: name

    def query_side_effect(sql, *args, **kwargs):
        m = MagicMock()
        if "subscription_packages" in sql and "SELECT" in sql:
            m.result.return_value = subs_rows
        elif "subscription_packages" in sql and "UPDATE" in sql:
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


def test_daily_cadence_subscription_receives_a_digest_every_run():
    subs_rows = [
        {"id": "s1", "user_id": "u1", "digest_cadence": "daily", "last_digest_sent_at": NOW - timedelta(days=1)},
    ]
    prefs_by_user = {"u1": {"channels_enabled": ["telegram"], "telegram_chat_id": "999"}}
    bq = _mock_bq(subs_rows, prefs_by_user)

    with patch("backend.digest_dispatcher.BigQueryHelper", return_value=bq), \
         patch("backend.digest_dispatcher.datetime") as mock_dt, \
         patch("backend.digest_dispatcher.bq_service.leaderboard", return_value=[]), \
         patch("backend.digest_dispatcher.bq_service.portfolio_summary", return_value={"total_pnl": 100.0}), \
         patch("backend.digest_dispatcher.send_telegram") as mock_send:
        mock_dt.now.return_value = NOW
        sent_ids = dispatch_digests()

    assert sent_ids == ["s1"]
    assert mock_send.call_count == 1


def test_alternate_cadence_skips_if_sent_yesterday_but_sends_after_two_days():
    subs_rows = [
        {"id": "s1", "user_id": "u1", "digest_cadence": "alternate", "last_digest_sent_at": NOW - timedelta(days=1)},
        {"id": "s2", "user_id": "u2", "digest_cadence": "alternate", "last_digest_sent_at": NOW - timedelta(days=2)},
    ]
    prefs_by_user = {
        "u1": {"channels_enabled": ["telegram"], "telegram_chat_id": "111"},
        "u2": {"channels_enabled": ["telegram"], "telegram_chat_id": "222"},
    }
    bq = _mock_bq(subs_rows, prefs_by_user)

    with patch("backend.digest_dispatcher.BigQueryHelper", return_value=bq), \
         patch("backend.digest_dispatcher.datetime") as mock_dt, \
         patch("backend.digest_dispatcher.bq_service.leaderboard", return_value=[]), \
         patch("backend.digest_dispatcher.bq_service.portfolio_summary", return_value={"total_pnl": 100.0}), \
         patch("backend.digest_dispatcher.send_telegram") as mock_send:
        mock_dt.now.return_value = NOW
        sent_ids = dispatch_digests()

    assert sent_ids == ["s2"]
    assert mock_send.call_count == 1


def test_weekly_cadence_skips_until_seven_days_have_passed():
    subs_rows = [
        {"id": "s1", "user_id": "u1", "digest_cadence": "weekly", "last_digest_sent_at": NOW - timedelta(days=6)},
        {"id": "s2", "user_id": "u2", "digest_cadence": "weekly", "last_digest_sent_at": NOW - timedelta(days=7)},
    ]
    prefs_by_user = {
        "u1": {"channels_enabled": ["telegram"], "telegram_chat_id": "111"},
        "u2": {"channels_enabled": ["telegram"], "telegram_chat_id": "222"},
    }
    bq = _mock_bq(subs_rows, prefs_by_user)

    with patch("backend.digest_dispatcher.BigQueryHelper", return_value=bq), \
         patch("backend.digest_dispatcher.datetime") as mock_dt, \
         patch("backend.digest_dispatcher.bq_service.leaderboard", return_value=[]), \
         patch("backend.digest_dispatcher.bq_service.portfolio_summary", return_value={"total_pnl": 100.0}), \
         patch("backend.digest_dispatcher.send_telegram") as mock_send:
        mock_dt.now.return_value = NOW
        sent_ids = dispatch_digests()

    assert sent_ids == ["s2"]
    assert mock_send.call_count == 1


def test_never_sent_digest_is_due_immediately_regardless_of_cadence():
    subs_rows = [
        {"id": "s1", "user_id": "u1", "digest_cadence": "weekly", "last_digest_sent_at": None},
    ]
    prefs_by_user = {"u1": {"channels_enabled": ["telegram"], "telegram_chat_id": "111"}}
    bq = _mock_bq(subs_rows, prefs_by_user)

    with patch("backend.digest_dispatcher.BigQueryHelper", return_value=bq), \
         patch("backend.digest_dispatcher.datetime") as mock_dt, \
         patch("backend.digest_dispatcher.bq_service.leaderboard", return_value=[]), \
         patch("backend.digest_dispatcher.bq_service.portfolio_summary", return_value={"total_pnl": 100.0}), \
         patch("backend.digest_dispatcher.send_telegram") as mock_send:
        mock_dt.now.return_value = NOW
        sent_ids = dispatch_digests()

    assert sent_ids == ["s1"]
    assert mock_send.call_count == 1


def test_sent_subscription_has_last_digest_sent_at_updated():
    subs_rows = [
        {"id": "s1", "user_id": "u1", "digest_cadence": "daily", "last_digest_sent_at": NOW - timedelta(days=1)},
    ]
    prefs_by_user = {"u1": {"channels_enabled": ["telegram"], "telegram_chat_id": "111"}}
    bq = _mock_bq(subs_rows, prefs_by_user)

    with patch("backend.digest_dispatcher.BigQueryHelper", return_value=bq), \
         patch("backend.digest_dispatcher.datetime") as mock_dt, \
         patch("backend.digest_dispatcher.bq_service.leaderboard", return_value=[]), \
         patch("backend.digest_dispatcher.bq_service.portfolio_summary", return_value={"total_pnl": 100.0}), \
         patch("backend.digest_dispatcher.send_telegram"):
        mock_dt.now.return_value = NOW
        dispatch_digests()

    update_calls = [c for c in bq.client.query.call_args_list if "UPDATE" in c[0][0]]
    assert len(update_calls) == 1
    assert "s1" in update_calls[0][0][0]
    assert NOW.isoformat() in update_calls[0][0][0]
