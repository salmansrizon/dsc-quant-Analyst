"""Offline tests for JWT-claim identity — no BigQuery on the auth hot path (#42)."""
import pytest
from fastapi.security import HTTPAuthorizationCredentials

from backend import auth


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_token_round_trips_identity_claims():
    token = auth.create_access_token(
        "user-1", "admin", email="a@x.com", phone="123", full_name="Ada", created_at="2026-01-01",
    )
    payload = auth.decode_token(token)
    assert payload["sub"] == "user-1"
    assert payload["role"] == "admin"
    assert payload["email"] == "a@x.com"
    assert payload["phone"] == "123"
    assert payload["full_name"] == "Ada"


def test_get_current_user_uses_claims_without_db(monkeypatch):
    # If the DB is touched, this blows up — proving the hot path never queries.
    import backend.user_service as us
    monkeypatch.setattr(us, "get_user_by_id", lambda _uid: pytest.fail("hit BigQuery"))

    token = auth.create_access_token(
        "user-1", "user", email="a@x.com", phone="123", full_name="Ada",
    )
    user = auth.get_current_user(_creds(token))
    assert user.id == "user-1"
    assert user.email == "a@x.com"
    assert user.role == "user"
    assert user.full_name == "Ada"


def test_admin_claim_flows_through_require_admin():
    token = auth.create_access_token("u", "admin", email="a@x.com")
    admin = auth.require_admin(auth.get_current_user(_creds(token)))
    assert admin.role == "admin"

    non_admin_token = auth.create_access_token("u2", "user", email="b@x.com")
    with pytest.raises(Exception):
        auth.require_admin(auth.get_current_user(_creds(non_admin_token)))


def test_legacy_token_without_email_falls_back_to_db(monkeypatch):
    from backend.models import UserResponse
    import backend.user_service as us

    called = {"n": 0}

    def fake_lookup(uid):
        called["n"] += 1
        return UserResponse(id=uid, email="legacy@x.com", phone="", full_name="Legacy", role="user")

    monkeypatch.setattr(us, "get_user_by_id", fake_lookup)

    # Legacy token: no identity claims (only sub/role).
    import jwt
    from datetime import datetime, timedelta, timezone
    legacy = jwt.encode(
        {"sub": "old-1", "role": "user",
         "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        auth.SECRET_KEY, algorithm=auth.ALGORITHM,
    )
    user = auth.get_current_user(_creds(legacy))
    assert user.email == "legacy@x.com"
    assert called["n"] == 1  # fell back exactly once
