"""Telegram + WhatsApp provider adapters (#94). Direct unit coverage of the raw
senders in backend/notifications/channels.py — test_notifier_channels.py covers
the fan-out layer above this with these functions mocked away; nothing there
exercises the actual request construction or missing-config/error paths."""
import requests

from backend.notifications import channels
from backend.tests.fakes import FakeResponse


def test_send_telegram_returns_false_without_a_bot_token(monkeypatch):
    monkeypatch.setattr(channels, "TELEGRAM_TOKEN", "")
    posted = []
    monkeypatch.setattr(requests, "post", lambda *a, **k: posted.append(1) or FakeResponse(200))
    assert channels.send_telegram("123", "hi") is False
    assert posted == []                            # never even tried


def test_send_telegram_posts_to_the_bot_api_with_chat_id_and_text(monkeypatch):
    monkeypatch.setattr(channels, "TELEGRAM_TOKEN", "t0k3n")
    calls = []
    def fake_post(url, json=None, timeout=None):
        calls.append((url, json, timeout))
        return FakeResponse(200)
    monkeypatch.setattr(requests, "post", fake_post)

    assert channels.send_telegram("456", "Price Alert Triggered") is True
    url, payload, timeout = calls[0]
    assert url == "https://api.telegram.org/bott0k3n/sendMessage"
    assert payload == {"chat_id": "456", "text": "Price Alert Triggered"}
    assert timeout == 10


def test_send_telegram_returns_false_on_a_non_200(monkeypatch):
    monkeypatch.setattr(channels, "TELEGRAM_TOKEN", "t0k3n")
    monkeypatch.setattr(requests, "post",
                        lambda *a, **k: FakeResponse(400, "Bad Request: chat not found"))
    assert channels.send_telegram("999", "hi") is False


def test_send_whatsapp_returns_false_without_token_or_phone_id(monkeypatch):
    monkeypatch.setattr(channels, "WHATSAPP_TOKEN", "")
    monkeypatch.setattr(channels, "WHATSAPP_PHONE_ID", "pid1")
    posted = []
    monkeypatch.setattr(requests, "post", lambda *a, **k: posted.append(1) or FakeResponse(200))
    assert channels.send_whatsapp("+8801700000000", "hi") is False
    assert posted == []

    monkeypatch.setattr(channels, "WHATSAPP_TOKEN", "tok")
    monkeypatch.setattr(channels, "WHATSAPP_PHONE_ID", "")
    assert channels.send_whatsapp("+8801700000000", "hi") is False
    assert posted == []


def test_send_whatsapp_posts_the_meta_cloud_api_payload(monkeypatch):
    monkeypatch.setattr(channels, "WHATSAPP_TOKEN", "tok")
    monkeypatch.setattr(channels, "WHATSAPP_PHONE_ID", "pid1")
    calls = []
    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append((url, headers, json, timeout))
        return FakeResponse(200)
    monkeypatch.setattr(requests, "post", fake_post)

    assert channels.send_whatsapp("+8801700000000", "hello") is True
    url, headers, payload, timeout = calls[0]
    assert url == "https://graph.facebook.com/v18.0/pid1/messages"
    assert headers["Authorization"] == "Bearer tok"
    assert payload == {
        "messaging_product": "whatsapp", "to": "+8801700000000",
        "type": "text", "text": {"body": "hello"},
    }
    assert timeout == 10


def test_send_whatsapp_returns_false_on_a_non_200(monkeypatch):
    monkeypatch.setattr(channels, "WHATSAPP_TOKEN", "tok")
    monkeypatch.setattr(channels, "WHATSAPP_PHONE_ID", "pid1")
    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResponse(401, "Invalid token"))
    assert channels.send_whatsapp("+8801700000000", "hi") is False
