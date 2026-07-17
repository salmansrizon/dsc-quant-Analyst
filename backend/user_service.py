import uuid
import pandas as pd
from datetime import datetime, timezone
from typing import Optional
from google.cloud import bigquery
from .models import UserResponse
from . import db

# Single shared client + table-name helper (ticket #41). Previously this module
# hardcoded PROJECT/DATASET, diverging from the env-driven config elsewhere.
# No module-level client: reads go through db.query_rows and writes through
# db.insert_rows, so the read path is stubbable via db._client (ticket #46).
PROJECT = db.PROJECT
DATASET = db.DATASET


def _insert_user_row(row: dict):
    db.insert_rows("users", [row])


def create_user(payload) -> UserResponse:
    from .auth import hash_password

    email = payload.email.strip().lower()
    existing = get_user_by_email(email)
    if existing:
        raise ValueError("Email already exists")

    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    hashed = hash_password(payload.password)

    _insert_user_row({
        "id": user_id,
        "email": email,
        "phone": payload.phone,
        "password_hash": hashed,
        "full_name": payload.full_name,
        "role": "user",
        "created_at": now,
        "updated_at": now,
    })

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
        FROM {db.table_id('users')}
        WHERE LOWER(email) = @email
        LIMIT 1
    """
    params = [bigquery.ScalarQueryParameter("email", "STRING", email.strip().lower())]
    rows = db.query_rows(sql, params)
    if not rows:
        return None
    r = rows[0]
    return UserResponse(
        id=r["id"],
        email=r["email"],
        phone=r.get("phone", ""),
        full_name=r.get("full_name", ""),
        role=r.get("role", "user"),
        created_at=str(r["created_at"]) if r.get("created_at") else None,
    )


def get_user_by_id(user_id: str) -> Optional[UserResponse]:
    sql = f"""
        SELECT id, email, phone, full_name, role, created_at
        FROM {db.table_id('users')}
        WHERE id = @uid
        LIMIT 1
    """
    params = [bigquery.ScalarQueryParameter("uid", "STRING", user_id)]
    rows = db.query_rows(sql, params)
    if not rows:
        return None
    r = rows[0]
    return UserResponse(
        id=r["id"],
        email=r["email"],
        phone=r.get("phone", ""),
        full_name=r.get("full_name", ""),
        role=r.get("role", "user"),
        created_at=str(r["created_at"]) if r.get("created_at") else None,
    )


def get_user_credentials(email: str) -> Optional[dict]:
    sql = f"""
        SELECT id, email, phone, password_hash, full_name, role
        FROM {db.table_id('users')}
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
        "password_hash": r.get("password_hash", ""),
        "role": r.get("role", "user"),
    }


def list_users():
    sql = f"""
        SELECT id, email, phone, full_name, role, created_at
        FROM {db.table_id('users')}
        ORDER BY created_at DESC
    """
    return db.query_rows(sql)


def update_user(user_id: str, updates: dict):
    # BROKEN — see ticket #50. This reads the whole table and rewrites it with
    # WRITE_TRUNCATE (the pattern #40 removed everywhere else), and the edit
    # itself is applied to a copy that is then discarded, so it is a no-op.
    # Left as-is here deliberately: #46 is a read-path change, and this needs
    # the scoped-DML rewrite plus the multi-user regression test #40 got.
    rows = list(db.client().query(f"SELECT * FROM {db.table_id('users')}").result())
    now = datetime.now(timezone.utc)
    for r in rows:
        d = dict(r)
        if d["id"] == user_id:
            for col in ("full_name", "phone", "role"):
                if col in updates:
                    d[col] = updates[col]
            d["updated_at"] = now
    df = pd.DataFrame([dict(r) for r in rows])
    full = f"{PROJECT}.{DATASET}.users"
    db.client().load_table_from_dataframe(df, full, job_config=bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )).result()


def delete_user(user_id: str):
    # BROKEN — see ticket #50. Whole-table truncate-and-reload; deleting the
    # last user truncates with an empty DataFrame.
    rows = list(db.client().query(f"SELECT * FROM {db.table_id('users')}").result())
    remaining = [dict(r) for r in rows if r["id"] != user_id]
    df = pd.DataFrame(remaining) if remaining else pd.DataFrame()
    full = f"{PROJECT}.{DATASET}.users"
    db.client().load_table_from_dataframe(df, full, job_config=bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )).result()
