from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from backend.api import app
from backend.auth import create_access_token
from backend.models import UserResponse
from backend import repositories
from backend.repositories import NotFoundError

USER_ID = "holdings-user-id"


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def user_token():
    return create_access_token(USER_ID, "user")


@pytest.fixture
def mock_user():
    return UserResponse(
        id=USER_ID, email="holdings@test.com", phone="01700000003",
        full_name="Holdings User", role="user",
    )


def test_watchlist_remove_missing_item_returns_404(client, user_token, mock_user):
    with patch("backend.user_service.get_user_by_id", return_value=mock_user), \
         patch.object(repositories.watchlist_repo, "remove", side_effect=NotFoundError("not found")):
        resp = client.delete(
            "/api/watchlist/GHOST",
            headers={"Authorization": f"Bearer {user_token}"},
        )
    assert resp.status_code == 404
