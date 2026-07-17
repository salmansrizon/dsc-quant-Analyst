"""Tests for the Admin export endpoints.

These hit real BigQuery (the exports stream whole tables), so they are slow and
require credentials.

Admin access is granted with FastAPI's dependency_overrides, not @patch:
FastAPI resolves Depends(require_admin) when the route is registered, so
patching the module attribute afterwards has no effect and every request
arrived unauthenticated (401). That is why these tests only ever errored at
setup or failed — they never exercised an export.
"""
import json

import pytest
from backend.api import app
from backend.auth import require_admin
from backend.models import UserResponse


@pytest.fixture
def admin_client(client):
    """A client whose requests are treated as an admin.

    `client` comes from conftest. Teardown pops only this override — clear()
    would wipe any other fixture's too.
    """
    app.dependency_overrides[require_admin] = lambda: UserResponse(
        id="test-admin", email="admin@example.invalid", phone="01700000000",
        full_name="Test Admin", role="admin", created_at=None,
    )
    yield client
    app.dependency_overrides.pop(require_admin, None)


@pytest.mark.integration
def test_admin_export_announcements(admin_client):
    resp = admin_client.get("/api/admin/export/announcements")
    assert resp.status_code == 200, resp.text
    assert "text/csv" in resp.headers.get("content-type", "")
    assert resp.headers["content-disposition"].startswith("attachment; filename=")

    csv_content = resp.content.decode("utf-8")
    assert "Symbol" in csv_content
    assert "Date" in csv_content
    # #49: this read a table that has never existed and returned a 404.
    assert "Announcement_Type" in csv_content


@pytest.mark.integration
def test_admin_export_price_archive(admin_client):
    resp = admin_client.get("/api/admin/export/price_archive")
    assert resp.status_code == 200, resp.text
    assert "text/csv" in resp.headers.get("content-type", "")
    assert resp.headers["content-disposition"].startswith("attachment; filename=")

    csv_content = resp.content.decode("utf-8")
    assert "Date" in csv_content
    assert "Symbol" in csv_content


@pytest.mark.integration
def test_admin_export_data_grid(admin_client):
    resp = admin_client.get("/api/admin/export/data_grid")
    assert resp.status_code == 200, resp.text
    assert "application/json" in resp.headers.get("content-type", "")

    data = resp.json()
    assert isinstance(data, list)
    assert data, "the datamatrix should not be empty — run dataGrid.py to seed it"
    assert "Symbol" in data[0]


def test_admin_export_requires_authentication(client):
    # No override here: the real require_admin must reject an anonymous caller.
    resp = client.get("/api/admin/export/announcements")
    assert resp.status_code == 401
