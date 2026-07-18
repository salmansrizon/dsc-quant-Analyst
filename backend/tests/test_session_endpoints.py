"""Offline tests for the #68 session + account-recovery endpoints.

Everything here monkeypatches the names api.py imported into its own module
namespace (`backend.api.<name>`) rather than the service modules they came
from — patching user_service.get_user_session after api.py already bound its
own reference to the old function would have no effect on the route, exactly
as test_admin_exports.py's dependency_overrides note explains for Depends.
"""
import pytest

from backend import api, auth
from backend.models import UserResponse


def _user(uid="user-1", email="a@x.com", role="user"):
    return UserResponse(id=uid, email=email, phone="", full_name="", role=role, created_at=None)


# ── logout / logout-all ─────────────────────────────────────────────────────

def test_logout_requires_authentication(client):
    resp = client.post("/api/auth/logout")
    assert resp.status_code == 401


def test_logout_is_a_documented_noop(client):
    app_ = api.app
    app_.dependency_overrides[auth.get_current_user] = lambda: _user()
    try:
        resp = client.post("/api/auth/logout")
    finally:
        app_.dependency_overrides.pop(auth.get_current_user, None)
    assert resp.status_code == 200
    assert "message" in resp.json()


def test_logout_all_bumps_token_version(client, monkeypatch):
    calls = []
    monkeypatch.setattr(api, "bump_token_version", lambda uid: calls.append(uid) or True)
    api.app.dependency_overrides[auth.get_current_user] = lambda: _user(uid="user-42")
    try:
        resp = client.post("/api/auth/logout-all")
    finally:
        api.app.dependency_overrides.pop(auth.get_current_user, None)
    assert resp.status_code == 200
    assert calls == ["user-42"]


# ── refresh ──────────────────────────────────────────────────────────────────

def test_refresh_reissues_both_tokens(client, monkeypatch):
    token = auth.create_refresh_token("user-1", token_version=0)
    monkeypatch.setattr(api, "get_user_session", lambda uid: {
        "id": "user-1", "email": "a@x.com", "password_hash": "h", "token_version": 0,
    })
    monkeypatch.setattr(api, "get_user_by_id", lambda uid: _user(uid="user-1"))

    resp = client.post("/api/auth/refresh", json={"refresh_token": token})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["access_token"] and data["refresh_token"]
    assert auth.decode_token(data["access_token"])["type"] == "access"
    assert auth.decode_token(data["refresh_token"])["type"] == "refresh"


def test_refresh_rejects_a_stale_token_version(client, monkeypatch):
    # The refresh token was issued under version 0; the account has since
    # bumped to version 1 (password reset or logout-all).
    token = auth.create_refresh_token("user-1", token_version=0)
    monkeypatch.setattr(api, "get_user_session", lambda uid: {
        "id": "user-1", "email": "a@x.com", "password_hash": "h", "token_version": 1,
    })
    resp = client.post("/api/auth/refresh", json={"refresh_token": token})
    assert resp.status_code == 401


def test_refresh_rejects_an_access_token(client):
    token = auth.create_access_token(_user())
    resp = client.post("/api/auth/refresh", json={"refresh_token": token})
    assert resp.status_code == 401


def test_refresh_rejects_an_unknown_user(client, monkeypatch):
    token = auth.create_refresh_token("ghost", token_version=0)
    monkeypatch.setattr(api, "get_user_session", lambda uid: None)
    resp = client.post("/api/auth/refresh", json={"refresh_token": token})
    assert resp.status_code == 401


# ── forgot-password / reset-password ────────────────────────────────────────

def test_forgot_password_is_always_200_for_an_unknown_email(client, monkeypatch):
    monkeypatch.setattr(api, "get_user_by_email", lambda email: None)
    sent = []
    monkeypatch.setattr(api.account_recovery, "send_reset_email",
                        lambda *a, **k: sent.append(a) or True)
    resp = client.post("/api/auth/forgot-password", json={"email": "nobody@x.com"})
    assert resp.status_code == 200
    assert sent == [], "no account exists — nothing should be sent"


def test_forgot_password_sends_a_reset_link_for_a_known_account(client, monkeypatch):
    monkeypatch.setattr(api, "get_user_by_email", lambda email: _user(uid="user-1", email=email))
    monkeypatch.setattr(api, "get_user_session", lambda uid: {
        "id": uid, "email": "a@x.com", "password_hash": "hash-v1", "token_version": 0,
    })
    sent = []
    monkeypatch.setattr(api.account_recovery, "send_reset_email",
                        lambda uid, email, link: sent.append((uid, email, link)) or True)

    resp = client.post("/api/auth/forgot-password", json={"email": "a@x.com"})
    assert resp.status_code == 200
    assert len(sent) == 1
    uid, email, link = sent[0]
    assert uid == "user-1" and email == "a@x.com"
    assert "reset-password?token=" in link
    # The link's token must actually verify against the account it was minted for.
    token = link.split("token=")[1]
    payload = auth.decode_reset_token(token)
    auth.verify_reset_fingerprint(payload, "hash-v1")


def test_reset_password_success_bumps_version_via_the_service(client, monkeypatch):
    token = auth.create_reset_token("user-1", current_password_hash="hash-v1")
    monkeypatch.setattr(api, "get_user_session", lambda uid: {
        "id": uid, "email": "a@x.com", "password_hash": "hash-v1", "token_version": 0,
    })
    calls = []
    monkeypatch.setattr(api, "reset_password", lambda uid, new_hash: calls.append((uid, new_hash)) or True)

    resp = client.post("/api/auth/reset-password", json={"token": token, "new_password": "newpassword123"})
    assert resp.status_code == 200, resp.text
    assert len(calls) == 1 and calls[0][0] == "user-1"


def test_reset_password_rejects_a_used_token(client, monkeypatch):
    # Minted against hash-v1, but the account's current hash has since changed
    # (the token was already redeemed, or forged).
    token = auth.create_reset_token("user-1", current_password_hash="hash-v1")
    monkeypatch.setattr(api, "get_user_session", lambda uid: {
        "id": uid, "email": "a@x.com", "password_hash": "hash-v2", "token_version": 0,
    })
    calls = []
    monkeypatch.setattr(api, "reset_password", lambda uid, new_hash: calls.append((uid, new_hash)) or True)

    resp = client.post("/api/auth/reset-password", json={"token": token, "new_password": "newpassword123"})
    assert resp.status_code == 401
    assert calls == []


def test_reset_password_rejects_an_unknown_user(client, monkeypatch):
    token = auth.create_reset_token("ghost", current_password_hash="hash-v1")
    monkeypatch.setattr(api, "get_user_session", lambda uid: None)
    resp = client.post("/api/auth/reset-password", json={"token": token, "new_password": "newpassword123"})
    assert resp.status_code == 401


def test_reset_password_rejects_a_non_reset_token(client):
    token = auth.create_access_token(_user())
    resp = client.post("/api/auth/reset-password", json={"token": token, "new_password": "newpassword123"})
    assert resp.status_code == 401
