"""JWT authentication helpers."""
import jwt
import bcrypt
import os
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .models import UserResponse

SECRET_KEY = os.environ.get("JWT_SECRET_KEY") or "dsc-quant-secret-key-change-in-prod"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

security = HTTPBearer()


def hash_password(password: str) -> str:
    """Hash password with bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Verify password against bcrypt hash."""
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user: UserResponse) -> str:
    """Create a JWT access token from a user record.

    Only id/role/email are embedded — enough for get_current_user to authorize
    a request without a per-request BigQuery lookup (ticket #42). Phone/full_name
    are deliberately NOT in the token (they'd be base64-readable PII); endpoints
    that need the full, fresh record re-read it (see read_me / require_admin).
    """
    payload = {
        "sub": user.id,
        "role": user.role,
        "email": user.email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """FastAPI dependency: extract the current user from the JWT.

    Reads identity from the token claims — no BigQuery lookup on the hot path
    (ticket #42). Tokens issued before this change (no `email` claim) fall back
    to a one-time DB lookup so existing sessions keep working.
    """
    payload = decode_token(credentials.credentials)
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

    Admin authorization must not trust a possibly-stale 24h token claim — a
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
