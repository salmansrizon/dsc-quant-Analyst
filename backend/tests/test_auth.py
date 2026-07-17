"""Auth endpoint tests.

These sign up against real BigQuery, so they are marked `integration`. They are
also the only thing that catches a schema/type drift between the table and the
models — #51 (phone was INTEGER in BigQuery, a string in models.UserCreate) was
visible here and nowhere else. If CI ever runs only `-m "not integration"`, that
class of bug ships silently.
"""
import pytest

pytestmark = pytest.mark.integration


def test_signup_returns_token_and_user(client, test_email):
    resp = client.post("/api/auth/signup", json={
        "email": test_email,
        "phone": "01700000000",
        "password": "testpass123",
        "full_name": "Test User",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == test_email
    assert data["user"]["full_name"] == "Test User"
    assert data["user"]["role"] == "user"
    assert "id" in data["user"]

    # Cleanup
    from backend.user_service import delete_user
    delete_user(data["user"]["id"])


def test_login_valid_credentials_returns_token(client, created_user):
    resp = client.post("/api/auth/login", json={
        "email": created_user["email"],
        "password": "testpass123",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == created_user["email"]


def test_login_wrong_password_returns_401(client, created_user):
    resp = client.post("/api/auth/login", json={
        "email": created_user["email"],
        "password": "wrongpassword",
    })
    assert resp.status_code == 401


def test_login_unknown_email_returns_401(client):
    resp = client.post("/api/auth/login", json={
        "email": "nonexistent@example.com",
        "password": "somepass",
    })
    assert resp.status_code == 401


def test_signup_duplicate_email_returns_400(client, created_user):
    resp = client.post("/api/auth/signup", json={
        "email": created_user["email"],
        "phone": "01700000000",
        "password": "testpass123",
        "full_name": "Another User",
    })
    assert resp.status_code == 400


def test_me_with_valid_token_returns_user(client, created_user):
    resp = client.get("/api/auth/me", headers={
        "Authorization": f"Bearer {created_user['token']}",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == created_user["email"]
    assert data["role"] == "user"


def test_me_without_token_returns_401(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401