from unittest.mock import patch, MagicMock
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


PACKAGE = {
    "medium": ["telegram", "email"],
    "alert_channel": True,
    "digest_channel": True,
    "alert_cap": 50,
    "digest_cadence": "daily",
}


# ── Behavior 1: POST /api/subscriptions creates a pending subscription ────────

def test_create_subscription_returns_pending_status(client, user_token, mock_user):
    fake_sub = {"id": "sub-123", "status": "pending", "user_id": USER_ID}
    with patch("backend.user_service.get_user_by_id", return_value=mock_user), \
         patch("backend.bq_service.create_subscription", return_value=fake_sub):
        resp = client.post(
            "/api/subscriptions",
            json=PACKAGE,
            headers={"Authorization": f"Bearer {user_token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pending"
    assert "id" in data


# ── Behavior 2: attach transaction ID ────────────────────────────────────────

def test_attach_transaction_id_returns_transaction_id(client, user_token, mock_user):
    fake_result = {"id": "sub-123", "transaction_id": "BKS123456", "status": "pending"}
    with patch("backend.user_service.get_user_by_id", return_value=mock_user), \
         patch("backend.bq_service.attach_transaction_id", return_value=fake_result):
        resp = client.post(
            "/api/subscriptions/sub-123/transaction",
            json={"transaction_id": "BKS123456"},
            headers={"Authorization": f"Bearer {user_token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["transaction_id"] == "BKS123456"


def test_attach_transaction_id_rejects_empty_id(client, user_token, mock_user):
    with patch("backend.user_service.get_user_by_id", return_value=mock_user):
        resp = client.post(
            "/api/subscriptions/sub-123/transaction",
            json={"transaction_id": ""},
            headers={"Authorization": f"Bearer {user_token}"},
        )
    assert resp.status_code == 400


# ── Behavior 3: admin approve requires admin role ─────────────────────────────

def test_approve_subscription_returns_403_for_regular_user(client, user_token, mock_user):
    with patch("backend.user_service.get_user_by_id", return_value=mock_user):
        resp = client.post(
            "/api/admin/subscriptions/sub-123/approve",
            headers={"Authorization": f"Bearer {user_token}"},
        )
    assert resp.status_code == 403


def test_approve_subscription_succeeds_for_admin(client, admin_token, mock_admin):
    fake_result = {"id": "sub-123", "status": "active"}
    with patch("backend.user_service.get_user_by_id", return_value=mock_admin), \
         patch("backend.bq_service.decide_subscription", return_value=fake_result):
        resp = client.post(
            "/api/admin/subscriptions/sub-123/approve",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"


# ── Behavior 4: pricing endpoint returns weights and bundles ──────────────────

def test_pricing_returns_weights_and_bundles(client):
    fake_pricing = {
        "weights": [{"dimension": "medium", "key": "telegram", "weight_price": 50.0}],
        "bundles": [{"name": "Starter", "price": 200.0, "is_active": True}],
    }
    with patch("backend.bq_service.get_pricing", return_value=fake_pricing):
        resp = client.get("/api/subscriptions/pricing")
    assert resp.status_code == 200
    data = resp.json()
    assert "weights" in data
    assert "bundles" in data
    assert isinstance(data["weights"], list)
    assert isinstance(data["bundles"], list)
