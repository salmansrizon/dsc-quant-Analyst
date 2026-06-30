from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from backend.api import app
from backend.auth import create_access_token
from backend.models import UserResponse

USER_ID = "pref-user-id"


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def user_token():
    return create_access_token(USER_ID, "user")


@pytest.fixture
def mock_user():
    return UserResponse(
        id=USER_ID, email="pref@test.com", phone="01700000002",
        full_name="Pref User", role="user",
    )


PREFS = {
    "telegram_chat_id": "12345678",
    "whatsapp_number": "8801700000000",
    "email": "user@example.com",
    "web_push_subscription": None,
    "channels_enabled": ["telegram", "email"],
}


# ── Behavior 7: GET /api/settings/notifications requires auth ─────────────────

def test_get_notification_prefs_requires_auth(client):
    resp = client.get("/api/settings/notifications")
    assert resp.status_code in (401, 403)


def test_get_notification_prefs_returns_preferences(client, user_token, mock_user):
    with patch("backend.user_service.get_user_by_id", return_value=mock_user), \
         patch("backend.bq_service.get_notification_preferences", return_value=PREFS):
        resp = client.get(
            "/api/settings/notifications",
            headers={"Authorization": f"Bearer {user_token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "channels_enabled" in data
    assert "telegram" in data["channels_enabled"]


# ── Behavior 8: PUT /api/settings/notifications updates preferences ───────────

def test_update_notification_prefs_returns_updated_data(client, user_token, mock_user):
    updated = {**PREFS, "channels_enabled": ["telegram", "email", "web_push"]}
    with patch("backend.user_service.get_user_by_id", return_value=mock_user), \
         patch("backend.bq_service.update_notification_preferences", return_value=updated):
        resp = client.put(
            "/api/settings/notifications",
            json=PREFS,
            headers={"Authorization": f"Bearer {user_token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "channels_enabled" in data
