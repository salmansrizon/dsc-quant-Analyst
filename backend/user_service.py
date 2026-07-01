import uuid
from datetime import datetime, timezone
from typing import Optional
from google.cloud import bigquery
from google.api_core.exceptions import NotFound
from dotenv import load_dotenv
from .utils import bigquery_helper  # noqa: F401 — bootstraps GOOGLE_APPLICATION_CREDENTIALS from GCP_SERVICE_ACCOUNT_JSON
from .models import UserResponse

load_dotenv()

PROJECT = "dbt-test-420614"
DATASET = "lankabd_dataset"
bq = bigquery.Client(project=PROJECT)

def _uid(table: str) -> str:
    return f"`{PROJECT}.{DATASET}.{table}`"


def _row_to_json(row: dict) -> dict:
    return {k: v.isoformat() if hasattr(v, "isoformat") else v for k, v in row.items()}


def _insert_user_row(row: dict):
    full = f"{PROJECT}.{DATASET}.users"
    bq.load_table_from_json(
        [_row_to_json(row)], full,
        job_config=bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
            schema_update_options=[bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION],
        )
    ).result()


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
        FROM {_uid('users')}
        WHERE LOWER(email) = @email
        LIMIT 1
    """
    params = [bigquery.ScalarQueryParameter("email", "STRING", email.strip().lower())]
    try:
        rows = list(bq.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params)).result())
    except NotFound:
        return None
    if not rows:
        return None
    r = dict(rows[0])
    return UserResponse(
        id=r["id"],
        email=r["email"],
        phone=str(r.get("phone") or ""),
        full_name=r.get("full_name", ""),
        role=r.get("role", "user"),
        created_at=str(r["created_at"]) if r.get("created_at") else None,
    )


def get_user_by_id(user_id: str) -> Optional[UserResponse]:
    sql = f"""
        SELECT id, email, phone, full_name, role, created_at
        FROM {_uid('users')}
        WHERE id = @uid
        LIMIT 1
    """
    params = [bigquery.ScalarQueryParameter("uid", "STRING", user_id)]
    rows = list(bq.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params)).result())
    if not rows:
        return None
    r = dict(rows[0])
    return UserResponse(
        id=r["id"],
        email=r["email"],
        phone=str(r.get("phone") or ""),
        full_name=r.get("full_name", ""),
        role=r.get("role", "user"),
        created_at=str(r["created_at"]) if r.get("created_at") else None,
    )


def get_user_credentials(email: str) -> Optional[dict]:
    sql = f"""
        SELECT id, email, phone, password_hash, full_name, role
        FROM {_uid('users')}
        WHERE LOWER(email) = @email
        LIMIT 1
    """
    params = [bigquery.ScalarQueryParameter("email", "STRING", email.strip().lower())]
    try:
        rows = list(bq.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params)).result())
    except NotFound:
        return None
    if not rows:
        return None
    r = dict(rows[0])
    return {
        "id": r["id"],
        "email": r["email"],
        "password_hash": r.get("password_hash", ""),
        "role": r.get("role", "user"),
    }


def list_users():
    sql = f"""
        SELECT id, email, phone, full_name, role, created_at
        FROM {_uid('users')}
        ORDER BY created_at DESC
    """
    return [dict(r) for r in bq.query(sql).result()]


def update_user(user_id: str, updates: dict):
    rows = list(bq.query(f"SELECT * FROM {_uid('users')}").result())
    now = datetime.now(timezone.utc)
    updated = []
    for r in rows:
        d = dict(r)
        if d["id"] == user_id:
            for col in ("full_name", "phone", "role"):
                if col in updates:
                    d[col] = updates[col]
            d["updated_at"] = now
        updated.append(_row_to_json(d))
    full = f"{PROJECT}.{DATASET}.users"
    bq.load_table_from_json(
        updated, full,
        job_config=bigquery.LoadJobConfig(write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE)
    ).result()


def delete_user(user_id: str):
    rows = list(bq.query(f"SELECT * FROM {_uid('users')}").result())
    remaining = [_row_to_json(dict(r)) for r in rows if r["id"] != user_id]
    full = f"{PROJECT}.{DATASET}.users"
    if remaining:
        bq.load_table_from_json(
            remaining, full,
            job_config=bigquery.LoadJobConfig(write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE)
        ).result()