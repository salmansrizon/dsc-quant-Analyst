import uuid
from datetime import datetime, timezone
from typing import Optional
from google.cloud import bigquery
from .models import UserResponse
from . import db

# All BigQuery access goes through db (tickets #41/#46/#52): reads via
# db.query_rows against the `users_current` view, writes via db.append_version.
# No module-level client and no hardcoded project/dataset.

# Whitelist of admin-editable user columns. Anything outside this (id, email,
# password_hash, created_at) is not editable through the admin endpoint.
_USER_UPDATE_FIELDS = frozenset({"full_name", "phone", "role"})


def _to_user_response(r: dict) -> UserResponse:
    # `or ""` rather than .get(col, ""): the column exists but can be NULL, and
    # a default only applies to a missing key.
    return UserResponse(
        id=r["id"],
        email=r["email"],
        phone=r.get("phone") or "",
        full_name=r.get("full_name") or "",
        role=r.get("role") or "user",
        created_at=str(r["created_at"]) if r.get("created_at") else None,
    )


def create_user(payload) -> UserResponse:
    from .auth import hash_password

    email = payload.email.strip().lower()
    existing = get_user_by_email(email)
    if existing:
        raise ValueError("Email already exists")

    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    hashed = hash_password(payload.password)

    db.append_version("users", [{
        "id": user_id,
        "email": email,
        "phone": payload.phone,
        "password_hash": hashed,
        "full_name": payload.full_name,
        "role": "user",
        "token_version": 0,
        "created_at": now,
        "updated_at": now,
    }])

    return UserResponse(
        id=user_id,
        email=email,
        phone=payload.phone,
        full_name=payload.full_name,
        role="user",
        created_at=str(now),
    )


def get_user_by_email(email: str) -> Optional[UserResponse]:
    sql = f"""
        SELECT id, email, phone, full_name, role, created_at
        FROM {db.current_view('users')}
        WHERE LOWER(email) = @email
        LIMIT 1
    """
    params = [bigquery.ScalarQueryParameter("email", "STRING", email.strip().lower())]
    rows = db.query_rows(sql, params)
    if not rows:
        return None
    return _to_user_response(rows[0])


def get_user_by_id(user_id: str) -> Optional[UserResponse]:
    sql = f"""
        SELECT id, email, phone, full_name, role, created_at
        FROM {db.current_view('users')}
        WHERE id = @uid
        LIMIT 1
    """
    params = [bigquery.ScalarQueryParameter("uid", "STRING", user_id)]
    rows = db.query_rows(sql, params)
    if not rows:
        return None
    return _to_user_response(rows[0])


def get_user_credentials(email: str) -> Optional[dict]:
    sql = f"""
        SELECT id, email, phone, password_hash, full_name, role, token_version
        FROM {db.current_view('users')}
        WHERE LOWER(email) = @email
        LIMIT 1
    """
    params = [bigquery.ScalarQueryParameter("email", "STRING", email.strip().lower())]
    rows = db.query_rows(sql, params)
    if not rows:
        return None
    r = rows[0]
    return {
        "id": r["id"],
        "email": r["email"],
        "password_hash": r.get("password_hash") or "",
        "role": r.get("role") or "user",
        # NULL for every row appended before #68 added the column — 0 is the
        # documented default, not a guess.
        "token_version": r.get("token_version") or 0,
    }


def get_user_session(user_id: str) -> Optional[dict]:
    """password_hash + token_version for the session flows (#68): /refresh
    compares token_version, /reset-password checks the fingerprint against
    password_hash. Not exposed through UserResponse — those are session-only,
    not profile data.
    """
    row = _find_user_row(user_id)
    if not row:
        return None
    return {
        "id": row["id"],
        "email": row["email"],
        "password_hash": row.get("password_hash") or "",
        "token_version": row.get("token_version") or 0,
    }


def list_users():
    sql = f"""
        SELECT id, email, phone, full_name, role, created_at
        FROM {db.current_view('users')}
        ORDER BY created_at DESC
    """
    return db.query_rows(sql)


def _find_user_row(user_id: str) -> dict | None:
    """The user's full current row (including password_hash), or None."""
    return db.find_current("users", id=user_id)


def update_user(user_id: str, updates: dict) -> bool:
    """Update one user's editable columns. Returns whether a row changed.

    Appends a new version (#50, #52). This used to read the whole table and
    reload it with WRITE_TRUNCATE — the pattern #40 removed everywhere else —
    which erased any signup landing between the read and the load, and applied
    its edit to a copy that was then discarded, so it never changed anything.
    """
    changes = {k: v for k, v in updates.items() if k in _USER_UPDATE_FIELDS and v is not None}
    if not changes:
        return False

    row = _find_user_row(user_id)
    if not row:
        return False

    db.append_version("users", [{
        **row,
        **changes,
        "updated_at": datetime.now(timezone.utc),
    }])
    return True


def bump_token_version(user_id: str) -> bool:
    """Invalidate every outstanding refresh token for a user (#68).

    Used by logout-all. A refresh token carries the token_version it was
    issued under; /refresh compares that against the user's current value, so
    bumping it here fails every token issued before this call without a
    separate revocation list.
    """
    row = _find_user_row(user_id)
    if not row:
        return False

    db.append_version("users", [{
        **row,
        "token_version": (row.get("token_version") or 0) + 1,
        "updated_at": datetime.now(timezone.utc),
    }])
    return True


def reset_password(user_id: str, new_password_hash: str) -> bool:
    """Set a new password hash and bump token_version in the same version (#68).

    One append, not two: reset-password and logout-all both want the version
    bump, and a password reset should also kill every existing session, so the
    two changes land together rather than racing across separate writes.
    """
    row = _find_user_row(user_id)
    if not row:
        return False

    db.append_version("users", [{
        **row,
        "password_hash": new_password_hash,
        "token_version": (row.get("token_version") or 0) + 1,
        "updated_at": datetime.now(timezone.utc),
    }])
    return True


def delete_user(user_id: str) -> bool:
    """Tombstone one user. Returns whether they existed.

    The old whole-table reload dropped concurrent signups, and truncated the
    table with an empty DataFrame when the last user was removed (#50).
    """
    row = _find_user_row(user_id)
    if not row:
        return False

    db.tombstone("users", row)
    return True
