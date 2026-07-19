"""Append-only notification preferences (#78)."""
import json

import pytest

from backend import db, notification_prefs_service as nps
from backend.tests.fakes import AppendLog, FakeClient, rows as fake_rows


@pytest.fixture
def appended(monkeypatch):
    log = AppendLog()
    monkeypatch.setattr(db, "append_version", log)
    return log


def test_update_prefs_appends_a_version_keyed_by_user(appended, monkeypatch):
    # get_prefs (called at the end) reads the row back.
    monkeypatch.setattr(db, "_client", FakeClient(result_rows=fake_rows(
        {"id": "u1", "user_id": "u1", "channels_enabled": '["email","telegram"]',
         "telegram_chat_id": "c1"})))
    nps.update_prefs("u1", {"channels_enabled": ["email", "telegram"],
                            "telegram_chat_id": "c1"})
    row = appended.appends[0]["rows"][0]
    assert row["id"] == "u1"                                  # upsert key = user_id
    assert row["channels_enabled"] == '["email", "telegram"]'  # stored as JSON string


def test_get_prefs_parses_channels_enabled_to_a_list(monkeypatch):
    monkeypatch.setattr(db, "_client", FakeClient(result_rows=fake_rows(
        {"id": "u1", "user_id": "u1", "channels_enabled": '["email"]'})))
    assert nps.get_prefs("u1")["channels_enabled"] == ["email"]


def test_get_prefs_is_none_when_absent(monkeypatch):
    monkeypatch.setattr(db, "_client", FakeClient(result_rows=[]))
    assert nps.get_prefs("nobody") is None
