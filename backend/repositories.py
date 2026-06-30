import os
from datetime import datetime, timezone
from google.cloud import bigquery
from dotenv import load_dotenv

load_dotenv()

PROJECT = os.environ.get("BIGQUERY_PROJECT_ID") or "dbt-test-420614"
DATASET = os.environ.get("BIGQUERY_DATASET_ID") or "lankabd_dataset"

bq = bigquery.Client(project=PROJECT)


def _full_id(table: str) -> str:
    return f"`{PROJECT}.{DATASET}.{table}`"


class NotFoundError(Exception):
    """Raised when a scoped mutation matches zero rows."""


def _execute_dml(client, sql: str, params: list) -> int:
    job = client.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params))
    job.result()
    return job.num_dml_affected_rows or 0


class WatchlistRepo:
    def __init__(self, client):
        self._client = client

    def remove(self, user_id: str, symbol: str) -> None:
        sql = f"""
            UPDATE {_full_id('watchlists')}
            SET is_deleted = TRUE, updated_at = @now
            WHERE user_id = @uid AND symbol = @symbol AND is_deleted = FALSE
        """
        params = [
            bigquery.ScalarQueryParameter("uid", "STRING", user_id),
            bigquery.ScalarQueryParameter("symbol", "STRING", symbol),
            bigquery.ScalarQueryParameter("now", "TIMESTAMP", datetime.now(timezone.utc)),
        ]
        affected = _execute_dml(self._client, sql, params)
        if affected == 0:
            raise NotFoundError(f"watchlist item not found: {symbol}")


_PORTFOLIO_UPDATABLE_FIELDS = {
    "buy_price": "FLOAT64",
    "quantity": "INT64",
    "price_target": "FLOAT64",
    "stop_loss": "FLOAT64",
    "notes": "STRING",
}


class PortfolioRepo:
    def __init__(self, client):
        self._client = client

    def update(self, portfolio_id: str, user_id: str, fields: dict) -> None:
        unknown = set(fields) - set(_PORTFOLIO_UPDATABLE_FIELDS)
        if unknown:
            raise ValueError(f"not updatable: {unknown}")

        set_clause = ", ".join(f"{k} = @{k}" for k in fields)
        sql = f"""
            UPDATE {_full_id('portfolios')}
            SET {set_clause}, updated_at = @now
            WHERE id = @pid AND user_id = @uid AND is_deleted = FALSE
        """
        params = [
            bigquery.ScalarQueryParameter(k, _PORTFOLIO_UPDATABLE_FIELDS[k], v)
            for k, v in fields.items()
        ] + [
            bigquery.ScalarQueryParameter("pid", "STRING", portfolio_id),
            bigquery.ScalarQueryParameter("uid", "STRING", user_id),
            bigquery.ScalarQueryParameter("now", "TIMESTAMP", datetime.now(timezone.utc)),
        ]
        affected = _execute_dml(self._client, sql, params)
        if affected == 0:
            raise NotFoundError(f"portfolio item not found: {portfolio_id}")

    def delete(self, portfolio_id: str, user_id: str) -> None:
        sql = f"""
            UPDATE {_full_id('portfolios')}
            SET is_deleted = TRUE, updated_at = @now
            WHERE id = @pid AND user_id = @uid AND is_deleted = FALSE
        """
        params = [
            bigquery.ScalarQueryParameter("pid", "STRING", portfolio_id),
            bigquery.ScalarQueryParameter("uid", "STRING", user_id),
            bigquery.ScalarQueryParameter("now", "TIMESTAMP", datetime.now(timezone.utc)),
        ]
        affected = _execute_dml(self._client, sql, params)
        if affected == 0:
            raise NotFoundError(f"portfolio item not found: {portfolio_id}")


class AlertRepo:
    def __init__(self, client):
        self._client = client

    def delete(self, alert_id: str, user_id: str) -> None:
        sql = f"""
            DELETE FROM {_full_id('price_alerts')}
            WHERE id = @aid AND user_id = @uid
        """
        params = [
            bigquery.ScalarQueryParameter("aid", "STRING", alert_id),
            bigquery.ScalarQueryParameter("uid", "STRING", user_id),
        ]
        affected = _execute_dml(self._client, sql, params)
        if affected == 0:
            raise NotFoundError(f"alert not found: {alert_id}")


watchlist_repo = WatchlistRepo(bq)
portfolio_repo = PortfolioRepo(bq)
alert_repo = AlertRepo(bq)
