import pytest
from fastapi.testclient import TestClient
from backend.api import app


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
        "phone": "1234567890",
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