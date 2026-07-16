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


def create_access_token(
    user_id: str,
    role: str,
    email: str | None = None,
    phone: str | None = None,
    full_name: str | None = None,
    created_at: str | None = None,
) -> str:
    """Create a JWT access token.

    Identity fields (email/phone/full_name) are embedded as claims so that
    get_current_user can reconstruct the user from the token without a
    per-request BigQuery lookup (ticket #42).
    """
    payload = {
        "sub": user_id,
        "role": role,
        "email": email,
        "phone": phone,
        "full_name": full_name,
        "created_at": created_at,
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
    if payload.get("email"):
        return UserResponse(
            id=payload.get("sub"),
            email=payload["email"],
            phone=payload.get("phone") or "",
            full_name=payload.get("full_name") or "",
            role=payload.get("role", "user"),
            created_at=payload.get("created_at"),
        )

    # Legacy token without identity claims — one-time DB lookup.
    from .user_service import get_user_by_id  # local import to avoid circular deps
    user = get_user_by_id(payload.get("sub"))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def require_admin(current_user = Depends(get_current_user)):
    """FastAPI dependency: require admin role."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user
