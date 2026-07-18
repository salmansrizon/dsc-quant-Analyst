"""Offline tests for JWT-claim identity — no BigQuery on the auth hot path (#42)."""
import jwt
import pytest
from datetime import datetime, timedelta, timezone
from fastapi.security import HTTPAuthorizationCredentials

from backend import auth
from backend.models import UserResponse


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def _user(role="user", uid="user-1", email="a@x.com"):
    return UserResponse(id=uid, email=email, phone="123", full_name="Ada", role=role)


def test_token_embeds_only_lightweight_identity():
    token = auth.create_access_token(_user(role="admin"))
    payload = auth.decode_token(token)
    assert payload["sub"] == "user-1"
    assert payload["role"] == "admin"
    assert payload["email"] == "a@x.com"
    # PII stays out of the token.
    assert "phone" not in payload
    assert "full_name" not in payload


def test_get_current_user_uses_claims_without_db(monkeypatch):
    # If the DB is touched, this blows up — proving the hot path never queries.
    import backend.user_service as us
    monkeypatch.setattr(us, "get_user_by_id", lambda _uid: pytest.fail("hit BigQuery"))

    user = auth.get_current_user(_creds(auth.create_access_token(_user())))
    assert user.id == "user-1"
    assert user.email == "a@x.com"
    assert user.role == "user"


def test_missing_sub_is_401():
    token = jwt.encode(
        {"role": "user", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        auth.SECRET_KEY, algorithm=auth.ALGORITHM,
    )
    with pytest.raises(Exception) as exc:
        auth.get_current_user(_creds(token))
    assert getattr(exc.value, "status_code", None) == 401


def test_require_admin_reverifies_and_allows_current_admin(monkeypatch):
    import backend.user_service as us
    monkeypatch.setattr(us, "get_user_by_id", lambda _uid: _user(role="admin"))
    admin = auth.require_admin(auth.get_current_user(_creds(auth.create_access_token(_user(role="admin")))))
    assert admin.role == "admin"


def test_require_admin_rejects_stale_admin_token(monkeypatch):
    # Token still claims admin, but the DB now says the user was demoted.
    import backend.user_service as us
    monkeypatch.setattr(us, "get_user_by_id", lambda _uid: _user(role="user"))
    stale_admin = auth.get_current_user(_creds(auth.create_access_token(_user(role="admin"))))
    with pytest.raises(Exception) as exc:
        auth.require_admin(stale_admin)
    assert getattr(exc.value, "status_code", None) == 403


# ── access/refresh/reset token types (#68) ──────────────────────────────────

def test_access_token_carries_type_access():
    payload = auth.decode_token(auth.create_access_token(_user()))
    assert payload["type"] == "access"


def test_refresh_token_carries_type_and_version():
    token = auth.create_refresh_token("user-1", token_version=3)
    payload = auth.decode_token(token)
    assert payload["sub"] == "user-1"
    assert payload["type"] == "refresh"
    assert payload["token_version"] == 3
    # No PII/role in a refresh token — it only ever mints a new pair.
    assert "role" not in payload and "email" not in payload


def test_decode_access_token_rejects_a_refresh_token():
    token = auth.create_refresh_token("user-1", token_version=0)
    with pytest.raises(Exception) as exc:
        auth.decode_access_token(token)
    assert getattr(exc.value, "status_code", None) == 401


def test_decode_access_token_accepts_a_legacy_token_with_no_type():
    legacy = jwt.encode(
        {"sub": "old-1", "role": "user",
         "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        auth.SECRET_KEY, algorithm=auth.ALGORITHM,
    )
    payload = auth.decode_access_token(legacy)
    assert payload["sub"] == "old-1"


def test_decode_refresh_token_rejects_an_access_token():
    token = auth.create_access_token(_user())
    with pytest.raises(Exception) as exc:
        auth.decode_refresh_token(token)
    assert getattr(exc.value, "status_code", None) == 401


def test_get_current_user_rejects_a_refresh_token_used_as_access():
    token = auth.create_refresh_token("user-1", token_version=0)
    with pytest.raises(Exception) as exc:
        auth.get_current_user(_creds(token))
    assert getattr(exc.value, "status_code", None) == 401


def test_reset_token_round_trips_purpose_and_fingerprint():
    token = auth.create_reset_token("user-1", current_password_hash="hash-v1")
    payload = auth.decode_reset_token(token)
    assert payload["sub"] == "user-1"
    assert payload["purpose"] == "reset"
    auth.verify_reset_fingerprint(payload, "hash-v1")  # must not raise


def test_reset_token_fingerprint_fails_after_the_password_changes():
    """Single-use: once reset succeeds, password_hash changes, and the same
    token's embedded fingerprint no longer matches (#68)."""
    token = auth.create_reset_token("user-1", current_password_hash="hash-v1")
    payload = auth.decode_reset_token(token)
    with pytest.raises(Exception) as exc:
        auth.verify_reset_fingerprint(payload, "hash-v2")
    assert getattr(exc.value, "status_code", None) == 401


def test_decode_reset_token_rejects_a_non_reset_token():
    token = auth.create_access_token(_user())
    with pytest.raises(Exception) as exc:
        auth.decode_reset_token(token)
    assert getattr(exc.value, "status_code", None) == 401


def test_legacy_token_without_email_falls_back_to_db(monkeypatch):
    import backend.user_service as us
    called = {"n": 0}

    def fake_lookup(uid):
        called["n"] += 1
        return _user(uid=uid, email="legacy@x.com")

    monkeypatch.setattr(us, "get_user_by_id", fake_lookup)
    legacy = jwt.encode(
        {"sub": "old-1", "role": "user", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        auth.SECRET_KEY, algorithm=auth.ALGORITHM,
    )
    user = auth.get_current_user(_creds(legacy))
    assert user.email == "legacy@x.com"
    assert called["n"] == 1
