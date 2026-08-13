"""Shared test doubles for the offline tests.

Mostly BigQuery fakes — stub `db._client` with one of these and every service
module goes through it, reads via db.query_rows, writes via
db.execute_dml/insert_rows (tickets #40/#46). Rows are real `bigquery.Row`
objects, not dicts: that is what the client library actually yields, and it is
the only reason db.query_rows' `dict(r)` conversion exists. Fakes that hand
back dicts make that conversion untested.

`FakeResponse` (#94) is the one non-BigQuery fake here — a `requests.Response`
stand-in for the outbound HTTP senders (email/Telegram/WhatsApp).
"""
from google.cloud import bigquery


def row(mapping: dict) -> bigquery.Row:
    """A real bigquery.Row, as the client library would return it."""
    return bigquery.Row(tuple(mapping.values()), {k: i for i, k in enumerate(mapping)})


def rows(*mappings: dict) -> list:
    return [row(m) for m in mappings]


class FakeJob:
    def __init__(self, result_rows=(), num_dml_affected_rows=1):
        self._rows = list(result_rows)
        self.num_dml_affected_rows = num_dml_affected_rows

    def result(self):
        return self._rows


class FakeClient:
    """Records every query() call and replays canned rows.

    `calls` holds one dict per query: the whitespace-normalized SQL and the
    parameters by name, so a test can assert values were bound rather than
    interpolated into the SQL text.
    """

    def __init__(self, result_rows=(), num_dml_affected_rows=1):
        self.calls = []
        self.result_rows = list(result_rows)
        self.num_dml_affected_rows = num_dml_affected_rows

    def query(self, sql, job_config=None):
        params = {}
        if job_config is not None:
            for p in job_config.query_parameters:
                # Scalars expose .value; ArrayQueryParameter exposes .values.
                params[p.name] = p.value if hasattr(p, "value") else list(p.values)
        self.calls.append({"sql": " ".join(sql.split()), "params": params})
        return FakeJob(self.result_rows, self.num_dml_affected_rows)


class AppendLog:
    """Captures db.append_version calls without touching BigQuery."""

    def __init__(self):
        self.appends = []

    def __call__(self, table, rows):
        self.appends.append({"table": table, "rows": [dict(r) for r in rows]})


class FakeResponse:
    """A `requests.Response` stand-in for the notification-channel senders
    (#94) — just the two attributes email_sender.py / channels.py read."""

    def __init__(self, status_code, text=""):
        self.status_code = status_code
        self.text = text


class VersionStore:
    """An append-only table plus the `_current` view semantics, in memory.

    Mirrors what BigQuery does: appends accumulate, and a read resolves the
    latest version per id and drops tombstones. Used by the survival tests,
    which have to assert on what actually SURVIVED — not on SQL text.
    """

    def __init__(self, initial=()):
        self.versions = [dict(r) for r in initial]

    def append(self, table, rows):
        self.versions.extend(dict(r) for r in rows)

    def current(self):
        latest = {}
        for row in self.versions:  # later appends win, as ORDER BY updated_at does
            latest[row["id"]] = row
        return [r for r in latest.values() if not r.get("is_deleted")]

    def current_for(self, **match):
        return [r for r in self.current()
                if all(r.get(k) == v for k, v in match.items())]
