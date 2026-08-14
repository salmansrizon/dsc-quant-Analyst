import pytest
from fastapi.testclient import TestClient
from backend.api import app
from backend import fit_service


@pytest.fixture(autouse=True)
def clear_fit_service_caches():
    # #106: fit_service.peer_metrics is lru_cache'd per (sector, day) across the
    # whole process — including across test files, since it's one Python
    # process for the whole run. Any test that (directly or via score_many /
    # sector_comparison_service) hits a real sector name with its own canned
    # mock data would silently read another test's cached result otherwise.
    fit_service._cached_peer_metrics.cache_clear()
    yield
    fit_service._cached_peer_metrics.cache_clear()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def test_email():
    import time
    return f"test-{int(time.time())}@example.com"


@pytest.fixture
def created_user(client, test_email):
    resp = client.post("/api/auth/signup", json={
        "email": test_email,
        "phone": "01700000000",
        "password": "testpass123",
        "full_name": "Test User",
    })
    assert resp.status_code == 200
    data = resp.json()
    yield {"email": test_email, "token": data["access_token"], "user": data["user"]}
    # Cleanup
    from backend.user_service import delete_user
    try:
        delete_user(data["user"]["id"])
    except Exception:
        pass