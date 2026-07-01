from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from backend.api import app
from backend.auth import create_access_token
from backend.models import UserResponse

USER_ID = "test-user-id"
ADMIN_ID = "test-admin-id"


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def user_token():
    return create_access_token(USER_ID, "user")


@pytest.fixture
def admin_token():
    return create_access_token(ADMIN_ID, "admin")


@pytest.fixture
def mock_user():
    return UserResponse(
        id=USER_ID, email="user@test.com", phone="01700000000",
        full_name="Test User", role="user",
    )


@pytest.fixture
def mock_admin():
    return UserResponse(
        id=ADMIN_ID, email="admin@test.com", phone="01700000001",
        full_name="Test Admin", role="admin",
    )


BUNDLE = {
    "name": "Starter",
    "medium": ["telegram", "email"],
    "alert_channel": True,
    "digest_channel": True,
    "alert_cap": 50,
    "digest_cadence": "daily",
    "price": 200.0,
}


# ── Behavior 1: POST /api/admin/bundles creates an active bundle ──────────────

def test_create_bundle_returns_active_bundle(client, admin_token, mock_admin):
    fake_bundle = {**BUNDLE, "id": "bundle-123", "is_active": True, "created_by": ADMIN_ID}
    with patch("backend.user_service.get_user_by_id", return_value=mock_admin), \
         patch("backend.bq_service.create_bundle", return_value=fake_bundle):
        resp = client.post(
            "/api/admin/bundles",
            json=BUNDLE,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_active"] is True
    assert data["name"] == "Starter"


# ── Behavior 2: only admins can create bundles ─────────────────────────────────

def test_create_bundle_returns_403_for_regular_user(client, user_token, mock_user):
    with patch("backend.user_service.get_user_by_id", return_value=mock_user):
        resp = client.post(
            "/api/admin/bundles",
            json=BUNDLE,
            headers={"Authorization": f"Bearer {user_token}"},
        )
    assert resp.status_code == 403


# ── Behavior 3: digest_cadence is validated against the allowed values ─────────

def test_create_bundle_rejects_invalid_digest_cadence(client, admin_token, mock_admin):
    bad_bundle = {**BUNDLE, "digest_cadence": "hourly"}
    with patch("backend.user_service.get_user_by_id", return_value=mock_admin):
        resp = client.post(
            "/api/admin/bundles",
            json=bad_bundle,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    assert resp.status_code == 422


# ── Behavior 4: GET /api/admin/bundles returns all bundles, including inactive ─

def test_list_bundles_returns_all_for_admin(client, admin_token, mock_admin):
    fake_bundles = [
        {**BUNDLE, "id": "bundle-1", "is_active": True},
        {**BUNDLE, "id": "bundle-2", "is_active": False},
    ]
    with patch("backend.user_service.get_user_by_id", return_value=mock_admin), \
         patch("backend.bq_service.list_bundles", return_value=fake_bundles):
        resp = client.get(
            "/api/admin/bundles",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert any(b["is_active"] is False for b in data)


def test_list_bundles_returns_403_for_regular_user(client, user_token, mock_user):
    with patch("backend.user_service.get_user_by_id", return_value=mock_user):
        resp = client.get(
            "/api/admin/bundles",
            headers={"Authorization": f"Bearer {user_token}"},
        )
    assert resp.status_code == 403


# ── Behavior 5: PUT /api/admin/bundles/{id} updates an existing bundle ─────────

def test_update_bundle_returns_updated_fields(client, admin_token, mock_admin):
    updated = {**BUNDLE, "id": "bundle-1", "price": 300.0, "is_active": True}
    with patch("backend.user_service.get_user_by_id", return_value=mock_admin), \
         patch("backend.bq_service.update_bundle", return_value=updated):
        resp = client.put(
            "/api/admin/bundles/bundle-1",
            json={**BUNDLE, "price": 300.0},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    assert resp.status_code == 200
    assert resp.json()["price"] == 300.0


def test_update_bundle_returns_403_for_regular_user(client, user_token, mock_user):
    with patch("backend.user_service.get_user_by_id", return_value=mock_user):
        resp = client.put(
            "/api/admin/bundles/bundle-1",
            json=BUNDLE,
            headers={"Authorization": f"Bearer {user_token}"},
        )
    assert resp.status_code == 403


# ── Behavior 6: POST /api/admin/bundles/{id}/deactivate flips is_active ────────

def test_deactivate_bundle_sets_inactive(client, admin_token, mock_admin):
    fake_result = {**BUNDLE, "id": "bundle-1", "is_active": False}
    with patch("backend.user_service.get_user_by_id", return_value=mock_admin), \
         patch("backend.bq_service.deactivate_bundle", return_value=fake_result):
        resp = client.post(
            "/api/admin/bundles/bundle-1/deactivate",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


def test_deactivate_bundle_returns_403_for_regular_user(client, user_token, mock_user):
    with patch("backend.user_service.get_user_by_id", return_value=mock_user):
        resp = client.post(
            "/api/admin/bundles/bundle-1/deactivate",
            headers={"Authorization": f"Bearer {user_token}"},
        )
    assert resp.status_code == 403
