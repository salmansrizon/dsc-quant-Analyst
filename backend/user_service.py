"""
User CRUD operations against BigQuery.
"""
import uuid
from datetime import datetime, timezone
from utils.bigquery_helper import BigQueryHelper
from auth import hash_password

bq = BigQueryHelper()
TABLE = "users"


def _ensure_table():
    """Create users table if not exists."""
    full_id = bq._get_full_table_id(TABLE)
    sql = f"""
    CREATE TABLE IF NOT EXISTS `{full_id}` (
        id STRING,
        email STRING,
        phone STRING,
        password_hash STRING,
        full_name STRING,
        role STRING,
        created_at TIMESTAMP,
        updated_at TIMESTAMP
    )
    """
    bq.client.query(sql).result()


def create_user(email: str, phone: str, password: str, full_name: str, role: str = "user") -> dict:
    """Insert new user. Returns user dict (no password_hash)."""
    _ensure_table()

    # Check duplicate email
    existing = get_user_by_email(email)
    if existing:
        raise ValueError("Email already registered")

    import pandas as pd
    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    pwd_hash = hash_password(password)

    user_data = {
        "id": [user_id],
        "email": [email],
        "phone": [phone],
        "password_hash": [pwd_hash],
        "full_name": [full_name],
        "role": [role],
        "created_at": [now],
        "updated_at": [now]
    }
    df = pd.DataFrame(user_data)
    bq.upload_dataframe(df, TABLE, "append")

    return {
        "id": user_id,
        "email": email,
        "phone": phone,
        "full_name": full_name,
        "role": role,
        "created_at": now.isoformat(),
    }


def get_user_by_email(email: str) -> dict | None:
    """Fetch user by email. Returns dict including password_hash."""
    full_id = bq._get_full_table_id(TABLE)
    sql = f"SELECT * FROM `{full_id}` WHERE email = '{email}' LIMIT 1"
    try:
        rows = list(bq.client.query(sql).result())
        if rows:
            return dict(rows[0])
        return None
    except Exception:
        return None


def get_user_by_id(user_id: str) -> dict | None:
    """Fetch user by id."""
    full_id = bq._get_full_table_id(TABLE)
    sql = f"SELECT id, email, phone, full_name, role, created_at, updated_at FROM `{full_id}` WHERE id = '{user_id}' LIMIT 1"
    try:
        rows = list(bq.client.query(sql).result())
        if rows:
            return dict(rows[0])
        return None
    except Exception:
        return None


def list_users() -> list:
    """List all users (admin use). No password_hash."""
    full_id = bq._get_full_table_id(TABLE)
    sql = f"SELECT id, email, phone, full_name, role, created_at, updated_at FROM `{full_id}` ORDER BY created_at DESC"
    try:
        rows = list(bq.client.query(sql).result())
        return [dict(r) for r in rows]
    except Exception:
        return []


def update_user(user_id: str, updates: dict) -> dict | None:
    """Update user fields. Returns updated user."""
    full_id = bq._get_full_table_id(TABLE)
    now = datetime.now(timezone.utc).isoformat()

    set_clauses = [f"updated_at = '{now}'"]
    for key, val in updates.items():
        if key in ("full_name", "phone", "role") and val is not None:
            set_clauses.append(f"{key} = '{val}'")

    sql = f"UPDATE `{full_id}` SET {', '.join(set_clauses)} WHERE id = '{user_id}'"
    bq.client.query(sql).result()
    return get_user_by_id(user_id)


def delete_user(user_id: str) -> bool:
    """Delete user by id."""
    full_id = bq._get_full_table_id(TABLE)
    sql = f"DELETE FROM `{full_id}` WHERE id = '{user_id}'"
    bq.client.query(sql).result()
    return True
