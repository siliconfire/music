"""Integration tests for the FastAPI application in main.py.

These tests use Starlette's TestClient (synchronous) and override the Spotify
dependency so no real Spotify credentials are required.
"""
import json
from unittest.mock import MagicMock

import pytest
from starlette.testclient import TestClient

import users as users_mod
import board as board_mod
from jwt import create_access_token
from tests.conftest import seed_users


# ---------------------------------------------------------------------------
# App + client fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def app():
    """Import the FastAPI app once per module."""
    from main import app as _app
    return _app


@pytest.fixture
def mock_spotify():
    """A minimal Spotify mock that satisfies endpoint code paths."""
    sp = MagicMock()
    sp.current_user_playing_track.return_value = {"is_playing": False, "item": None}
    sp.search.return_value = {"tracks": {"items": []}}
    return sp


@pytest.fixture
def client(app, users_db, board_db, mock_spotify):
    """
    TestClient with:
    - users.DB_FILE and board.BOARD_FILE redirected to temp files
    - Spotify dependency overridden with a mock
    """
    from main import get_sp, get_auth_manager

    app.dependency_overrides[get_sp] = lambda: mock_spotify
    app.dependency_overrides[get_auth_manager] = lambda: MagicMock()

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helper: create a user with a token
# ---------------------------------------------------------------------------

def _make_user(users_db, uid, name, perms, banned=False):
    seed_users(users_db, {"id": uid, "name": name, "permissions": perms, "banned": banned})
    return create_access_token(uid)


# ---------------------------------------------------------------------------
# /board — public endpoint
# ---------------------------------------------------------------------------

def test_get_board_no_auth(client):
    resp = client.get("/board")
    assert resp.status_code == 200
    data = resp.json()
    assert "widgets" in data
    assert "theme_key" in data


# ---------------------------------------------------------------------------
# /check — token validation
# ---------------------------------------------------------------------------

def test_check_invalid_token(client):
    resp = client.post("/check", headers={"X-Session-ID": "not-a-real-token"})
    assert resp.status_code == 200
    assert resp.json()["valid"] is False


def test_check_valid_token(client, users_db):
    token = _make_user(users_db, "user1", "Alice", ["music"])
    resp = client.post("/check", headers={"X-Session-ID": token})
    assert resp.status_code == 200
    assert resp.json()["valid"] is True


def test_check_no_token(client):
    resp = client.post("/check")
    assert resp.status_code == 200
    assert resp.json()["valid"] is False


# ---------------------------------------------------------------------------
# /token — login
# ---------------------------------------------------------------------------

def test_login_success(client, users_db):
    seed_users(users_db, {"id": "user1", "name": "Alice", "permissions": ["music"]})
    users_mod.set_user_password("user1", "correctpass")
    resp = client.post("/token", params={"user_id": "user1", "password": "correctpass"})
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


def test_login_wrong_password(client, users_db):
    seed_users(users_db, {"id": "user1", "name": "Alice", "permissions": ["music"]})
    users_mod.set_user_password("user1", "correctpass")
    resp = client.post("/token", params={"user_id": "user1", "password": "wrongpass"})
    assert resp.status_code == 401


def test_login_unknown_user(client, users_db):
    resp = client.post("/token", params={"user_id": "ghost", "password": "pass"})
    assert resp.status_code == 404


def test_login_no_user_id(client):
    resp = client.post("/token")
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# /me — authenticated endpoint
# ---------------------------------------------------------------------------

def test_me_requires_auth(client):
    resp = client.get("/me")
    assert resp.status_code == 403


def test_me_returns_user_info(client, users_db):
    token = _make_user(users_db, "user1", "Alice", ["music"])
    resp = client.get("/me", headers={"X-Session-ID": token})
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "user1"
    assert data["name"] == "Alice"


# ---------------------------------------------------------------------------
# /admin/users — admin-only endpoint
# ---------------------------------------------------------------------------

def test_admin_users_requires_admin(client, users_db):
    token = _make_user(users_db, "music1", "MusicUser", ["music"])
    resp = client.get("/admin/users", headers={"X-Session-ID": token})
    assert resp.status_code == 403


def test_admin_users_returns_list(client, users_db):
    token = _make_user(users_db, "admin1", "Admin", ["admin"])
    resp = client.get("/admin/users", headers={"X-Session-ID": token})
    assert resp.status_code == 200
    body = resp.json()
    # endpoint wraps the list in {"users": [...]}
    user_list = body if isinstance(body, list) else body.get("users", body)
    assert isinstance(user_list, list)
