from unittest.mock import patch, MagicMock
from backend.notifications.messages import build_alert_message, build_digest_message
from backend.notifications.channels import send_telegram


# ── Behavior 5: build_alert_message produces a non-empty string ───────────────

def test_alert_message_above_threshold_is_non_empty():
    msg = build_alert_message(symbol="ABBANK", ltp=45.5, target=45.0, direction="above")
    assert isinstance(msg, str)
    assert len(msg) > 0
    assert "ABBANK" in msg
    assert "45.50" in msg
    assert "above" in msg


def test_alert_message_below_threshold_contains_symbol():
    msg = build_alert_message(symbol="BRAC", ltp=30.0, target=35.0, direction="below")
    assert "BRAC" in msg
    assert "below" in msg


# ── Behavior 6: send_telegram constructs correct Bot API POST payload ──────────

def test_send_telegram_posts_to_correct_url():
    with patch("backend.notifications.channels.requests.post") as mock_post, \
         patch("backend.notifications.channels.TELEGRAM_TOKEN", "test-token-123"):
        mock_post.return_value = MagicMock(status_code=200)
        result = send_telegram(chat_id="99999", message="Test alert")

    assert result is True
    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args
    assert "api.telegram.org/bottest-token-123/sendMessage" in call_kwargs[0][0]
    payload = call_kwargs[1]["json"]
    assert payload["chat_id"] == "99999"
    assert payload["text"] == "Test alert"


# ── Behavior 7: build_digest_message produces a non-empty summary ─────────────

def test_digest_message_contains_portfolio_pnl_and_gainer_loser_symbols():
    msg = build_digest_message(
        portfolio_pnl=1250.75,
        top_gainers=[{"Symbol": "ACI", "ChangePct": 8.2}],
        top_losers=[{"Symbol": "BRAC", "ChangePct": -5.1}],
    )
    assert isinstance(msg, str)
    assert len(msg) > 0
    assert "1250.75" in msg
    assert "ACI" in msg
    assert "BRAC" in msg


def test_send_telegram_returns_false_without_token():
    with patch.dict("os.environ", {}, clear=True):
        import backend.notifications.channels as ch
        original = ch.TELEGRAM_TOKEN
        ch.TELEGRAM_TOKEN = ""
        result = send_telegram(chat_id="99999", message="Test")
        ch.TELEGRAM_TOKEN = original
    assert result is False
