"""JWT authentication helpers."""
import hashlib
import hmac
import jwt
import bcrypt
import os
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .models import UserResponse

_DEFAULT_SECRET = "dsc-quant-secret-key-change-in-prod"
_env_secret = os.environ.get("JWT_SECRET_KEY")

if not _env_secret and os.environ.get("VERCEL"):
    # #68 security launch-blocker: this default key is public in the repo's
    # history. Signed with it, a reset or refresh token is forgeable — anyone
    # can mint "reset password for user X" and take over the account. Fail at
    # import time rather than silently serving forgeable sessions in prod.
    raise RuntimeError(
        "JWT_SECRET_KEY is not set. Refusing to start with the default "
        "signing key on Vercel — see #68."
    )

SECRET_KEY = _env_secret or _DEFAULT_SECRET
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60          # 1h — the session model's short-lived leg (#68)
REFRESH_TOKEN_EXPIRE_DAYS = 30            # sliding window: /refresh reissues both
RESET_TOKEN_EXPIRE_MINUTES = 30

security = HTTPBearer()


def hash_password(password: str) -> str:
    """Hash password with bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Verify password against bcrypt hash."""
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user: UserResponse) -> str:
    """Create a short-lived (1h) JWT access token from a user record.

    Only id/role/email are embedded — enough for get_current_user to authorize
    a request without a per-request BigQuery lookup (ticket #42). Phone/full_name
    are deliberately NOT in the token (they'd be base64-readable PII); endpoints
    that need the full, fresh record re-read it (see read_me / require_admin).

    `type:"access"` distinguishes this from a refresh token (#68) — a refresh
    token used where an access token is expected must be rejected, and vice
    versa, so get_current_user checks it (see decode_access_token).
    """
    payload = {
        "sub": user.id,
        "role": user.role,
        "email": user.email,
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(user_id: str, token_version: int) -> str:
    """Create a 30-day refresh token carrying the user's `token_version` (#68).

    No role/email/PII — a refresh token only ever mints a new token pair, never
    authorizes a request directly. `token_version` is compared against the
    user's *current* value on every /refresh call: password-reset and
    logout-all bump it, which invalidates every refresh token issued before
    that bump without needing a revocation list.
    """
    payload = {
        "sub": user_id,
        "type": "refresh",
        "token_version": token_version,
        "exp": datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _fingerprint(password_hash: str) -> str:
    """HMAC of a password hash, keyed by the JWT secret — the reset token's
    single-use check (#68): the hash changes the moment a reset succeeds, so a
    reset token's embedded fingerprint stops matching after first use, with no
    separate "used" flag to store.
    """
    return hmac.new(SECRET_KEY.encode(), password_hash.encode(), hashlib.sha256).hexdigest()


def create_reset_token(user_id: str, current_password_hash: str) -> str:
    """Create a 30-minute password-reset token (#68), single-use by fingerprint."""
    payload = {
        "sub": user_id,
        "purpose": "reset",
        "fp": _fingerprint(current_password_hash),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate JWT token, regardless of type/purpose."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def decode_access_token(token: str) -> dict:
    """Decode a token for use as an access token; reject a refresh token.

    A token with no `type` claim is a pre-#68 access token — accepted, exactly
    as get_current_user already tolerates a pre-#42 token with no `email`.
    """
    payload = decode_token(token)
    if payload.get("type") == "refresh":
        raise HTTPException(status_code=401, detail="Refresh token cannot be used as an access token")
    return payload


def decode_refresh_token(token: str) -> dict:
    """Decode a token for use as a refresh token; reject anything else."""
    payload = decode_token(token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    return payload


def decode_reset_token(token: str) -> dict:
    """Decode a password-reset token and check its purpose (not its fingerprint).

    The fingerprint check needs the CURRENT password_hash, which only the
    caller (holding a fresh DB read) has — see verify_reset_fingerprint.
    """
    payload = decode_token(token)
    if payload.get("purpose") != "reset":
        raise HTTPException(status_code=401, detail="Invalid reset token")
    return payload


def verify_reset_fingerprint(payload: dict, current_password_hash: str) -> None:
    """Raise 401 unless the reset token's fingerprint matches the current hash.

    A mismatch means either a forged token or one already redeemed — the first
    successful reset changes password_hash, so a replayed token's embedded
    fingerprint no longer matches (#68's single-use guarantee).
    """
    if not hmac.compare_digest(payload.get("fp") or "", _fingerprint(current_password_hash)):
        raise HTTPException(status_code=401, detail="Reset token already used or invalid")


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """FastAPI dependency: extract the current user from the JWT.

    Reads identity from the token claims — no BigQuery lookup on the hot path
    (ticket #42). Tokens issued before this change (no `email` claim) fall back
    to a one-time DB lookup so existing sessions keep working.
    """
    payload = decode_access_token(credentials.credentials)
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Invalid token")

    if payload.get("email"):
        # Lightweight identity from claims — enough to authorize the request
        # without a DB hit. Phone/full_name aren't in the token; endpoints that
        # need them re-read the record.
        return UserResponse(
            id=sub,
            email=payload["email"],
            phone="",
            full_name="",
            role=payload.get("role", "user"),
            created_at=None,
        )

    # Legacy token without identity claims — one-time DB lookup.
    from .user_service import get_user_by_id  # local import to avoid circular deps
    user = get_user_by_id(sub)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def require_admin(current_user: UserResponse = Depends(get_current_user)):
    """Require admin role, re-verified against the DB.

    Admin authorization must not trust a possibly-stale access-token claim — a
    demoted admin should lose access immediately. This costs one DB read, but
    only on admin-gated endpoints, so the non-admin hot path stays DB-free
    (ticket #42 review).
    """
    from .user_service import get_user_by_id
    fresh = get_user_by_id(current_user.id)
    role = fresh.role if fresh else current_user.role
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return fresh or current_user
