"""Resend email adapter (#66/#94). No direct unit coverage existed before —
alert_checker's tests mock send_email away entirely."""
import pytest
import requests

from backend import email_sender
from backend.tests.fakes import FakeResponse


def test_send_email_raises_without_an_api_key(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="RESEND_API_KEY"):
        email_sender.send_email("u@example.com", "Alert", "<p>hi</p>")


def test_send_email_posts_to_resend_with_the_right_payload(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "key123")
    calls = []
    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append((url, headers, json, timeout))
        return FakeResponse(200)
    monkeypatch.setattr(requests, "post", fake_post)

    assert email_sender.send_email("u@example.com", "Price Alert", "<p>GP crossed 300</p>") is True
    url, headers, payload, timeout = calls[0]
    assert url == email_sender.RESEND_ENDPOINT
    assert headers["Authorization"] == "Bearer key123"
    assert payload["to"] == ["u@example.com"]
    assert payload["subject"] == "Price Alert"
    assert payload["html"] == "<p>GP crossed 300</p>"
    assert payload["from"] == email_sender.DEFAULT_FROM
    assert timeout == 10


def test_send_email_returns_false_when_resend_rejects_it(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "key123")
    monkeypatch.setattr(requests, "post",
                        lambda *a, **k: FakeResponse(422, "Invalid `from` address"))
    assert email_sender.send_email("u@example.com", "Alert", "<p>hi</p>") is False
