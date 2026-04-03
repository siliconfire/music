"""Tests for users.py."""
import json
import pytest
from fastapi import HTTPException

import users
from tests.conftest import seed_users


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _add_raw_user(db_path, uid, name, perms, banned=False, password=None):
    """Write or update a user entry directly in the DB file."""
    if db_path.exists():
        data = json.loads(db_path.read_text(encoding="utf-8"))
    else:
        data = {"users": {}}
    entry = {"name": name, "permissions": perms, "banned": banned, "reason": None}
    if password is not None:
        entry["password"] = password
    data["users"][str(uid)] = entry
    db_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# get_user_by_id / get_user
# ---------------------------------------------------------------------------

def test_get_user_returns_none_when_db_missing(users_db):
    result = users.get_user_by_id("1")
    assert result is None


def test_get_user_returns_user(users_db):
    seed_users(users_db, {"id": "1", "name": "Alice", "permissions": ["music"]})
    result = users.get_user_by_id("1")
    assert result is not None
    assert result["name"] == "Alice"


def test_get_user_unknown_id_returns_none(users_db):
    seed_users(users_db, {"id": "1", "name": "Alice", "permissions": []})
    assert users.get_user_by_id("99") is None


# ---------------------------------------------------------------------------
# Permission helpers
# ---------------------------------------------------------------------------

def test_rank_index_known_ranks():
    assert users._rank_index("music") == 0
    assert users._rank_index("admin") == 3
    assert users._rank_index("dev") == 5


def test_rank_index_unknown_returns_minus_one():
    assert users._rank_index("unknown_perm") == -1


def test_highest_rank_index_single_perm(users_db):
    seed_users(users_db, {"id": "1", "name": "Alice", "permissions": ["music"]})
    u = users.get_user_by_id("1")
    assert users.highest_rank_index(u) == 0


def test_highest_rank_index_multiple_perms(users_db):
    seed_users(users_db, {"id": "1", "name": "Alice", "permissions": ["music", "admin"]})
    u = users.get_user_by_id("1")
    assert users.highest_rank_index(u) == 3  # admin is index 3


def test_check_user_rank_or_higher_passes(users_db):
    seed_users(users_db, {"id": "1", "name": "Alice", "permissions": ["admin"]})
    assert users.check_user_rank_or_higher("1", "music") is True


def test_check_user_rank_or_higher_fails_for_higher_rank(users_db):
    seed_users(users_db, {"id": "1", "name": "Alice", "permissions": ["music"]})
    assert users.check_user_rank_or_higher("1", "admin") is False


def test_check_user_rank_or_higher_banned_user(users_db):
    seed_users(users_db, {"id": "1", "name": "Alice", "permissions": ["admin"], "banned": True})
    assert users.check_user_rank_or_higher("1", "music") is False


# ---------------------------------------------------------------------------
# create_user
# ---------------------------------------------------------------------------

def test_create_user_success(users_db):
    seed_users(users_db, {"id": "admin1", "name": "Admin", "permissions": ["superadmin"]})
    result = users.create_user("admin1", "new1", "New User", permissions=["music"])
    assert result["name"] == "New User"
    assert "music" in result["permissions"]


def test_create_user_requires_admin(users_db):
    seed_users(users_db, {"id": "mod1", "name": "Mod", "permissions": ["moderator"]})
    with pytest.raises(HTTPException) as exc:
        users.create_user("mod1", "new1", "New User")
    assert exc.value.status_code == 403


def test_create_user_duplicate_raises_409(users_db):
    seed_users(
        users_db,
        {"id": "admin1", "name": "Admin", "permissions": ["superadmin"]},
        {"id": "existing", "name": "Existing", "permissions": []},
    )
    with pytest.raises(HTTPException) as exc:
        users.create_user("admin1", "existing", "Another")
    assert exc.value.status_code == 409


def test_create_user_cannot_grant_own_rank(users_db):
    seed_users(users_db, {"id": "admin1", "name": "Admin", "permissions": ["admin"]})
    with pytest.raises(HTTPException) as exc:
        users.create_user("admin1", "new1", "New", permissions=["admin"])
    assert exc.value.status_code == 403


def test_create_user_actor_not_found(users_db):
    # Empty DB
    db_path_data = {"users": {}}
    users_db.write_text(json.dumps(db_path_data), encoding="utf-8")
    with pytest.raises(HTTPException) as exc:
        users.create_user("ghost", "new1", "New")
    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# delete_user
# ---------------------------------------------------------------------------

def test_delete_user_success(users_db):
    seed_users(
        users_db,
        {"id": "admin1", "name": "Admin", "permissions": ["superadmin"]},
        {"id": "user1", "name": "User", "permissions": ["music"]},
    )
    result = users.delete_user("admin1", "user1")
    assert result["id"] == "user1"
    assert users.get_user_by_id("user1") is None


def test_delete_user_cannot_delete_self(users_db):
    seed_users(users_db, {"id": "admin1", "name": "Admin", "permissions": ["superadmin"]})
    with pytest.raises(HTTPException) as exc:
        users.delete_user("admin1", "admin1")
    assert exc.value.status_code == 403


def test_delete_user_cannot_delete_higher_rank(users_db):
    seed_users(
        users_db,
        {"id": "admin1", "name": "Admin", "permissions": ["admin"]},
        {"id": "super1", "name": "Super", "permissions": ["superadmin"]},
    )
    with pytest.raises(HTTPException) as exc:
        users.delete_user("admin1", "super1")
    assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# ban_user / unban_user
# ---------------------------------------------------------------------------

def test_ban_user_success(users_db):
    seed_users(
        users_db,
        {"id": "admin1", "name": "Admin", "permissions": ["admin"]},
        {"id": "user1", "name": "User", "permissions": ["music"]},
    )
    result = users.ban_user("admin1", "user1", reason="Test ban")
    assert result["banned"] is True
    assert result["reason"] == "Test ban"


def test_ban_user_cannot_ban_self(users_db):
    seed_users(users_db, {"id": "admin1", "name": "Admin", "permissions": ["admin"]})
    with pytest.raises(HTTPException) as exc:
        users.ban_user("admin1", "admin1")
    assert exc.value.status_code == 403


def test_unban_user_success(users_db):
    seed_users(
        users_db,
        {"id": "admin1", "name": "Admin", "permissions": ["admin"]},
        {"id": "user1", "name": "User", "permissions": ["music"], "banned": True},
    )
    result = users.unban_user("admin1", "user1")
    assert result["banned"] is False


def test_banned_user_cannot_act(users_db):
    seed_users(
        users_db,
        {"id": "admin1", "name": "Admin", "permissions": ["admin"], "banned": True},
        {"id": "user1", "name": "User", "permissions": ["music"]},
    )
    with pytest.raises(HTTPException) as exc:
        users.ban_user("admin1", "user1")
    assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# add_permission / remove_permission
# ---------------------------------------------------------------------------

def test_add_permission_success(users_db):
    seed_users(
        users_db,
        {"id": "super1", "name": "Super", "permissions": ["superadmin"]},
        {"id": "user1", "name": "User", "permissions": []},
    )
    result = users.add_permission("super1", "user1", "music")
    assert "music" in result["permissions"]


def test_remove_permission_success(users_db):
    seed_users(
        users_db,
        {"id": "super1", "name": "Super", "permissions": ["superadmin"]},
        {"id": "user1", "name": "User", "permissions": ["music"]},
    )
    result = users.remove_permission("super1", "user1", "music")
    assert "music" not in result["permissions"]


def test_add_unknown_permission_raises_400(users_db):
    seed_users(users_db, {"id": "super1", "name": "Super", "permissions": ["superadmin"]})
    with pytest.raises(HTTPException) as exc:
        users.add_permission("super1", "user1", "nonexistent")
    assert exc.value.status_code == 400


# ---------------------------------------------------------------------------
# Password hashing and verification
# ---------------------------------------------------------------------------

def test_set_and_verify_password(users_db):
    seed_users(users_db, {"id": "user1", "name": "Alice", "permissions": ["music"]})
    users.set_user_password("user1", "mysecretpass")
    assert users.verify_user_password("user1", "mysecretpass") is True


def test_wrong_password_fails(users_db):
    seed_users(users_db, {"id": "user1", "name": "Alice", "permissions": ["music"]})
    users.set_user_password("user1", "mysecretpass")
    assert users.verify_user_password("user1", "wrongpass") is False


def test_password_starting_with_74_rejected(users_db):
    seed_users(users_db, {"id": "user1", "name": "Alice", "permissions": ["music"]})
    with pytest.raises(HTTPException) as exc:
        users.set_user_password("user1", "74invalid")
    assert exc.value.status_code == 400


def test_password_too_short_rejected(users_db):
    seed_users(users_db, {"id": "user1", "name": "Alice", "permissions": ["music"]})
    with pytest.raises(HTTPException) as exc:
        users.set_user_password("user1", "abc")
    assert exc.value.status_code == 400


def test_has_password_false_when_unset(users_db):
    seed_users(users_db, {"id": "user1", "name": "Alice", "permissions": []})
    u = users.get_user_by_id("user1")
    assert users.has_password(u) is False


def test_has_password_true_after_set(users_db):
    seed_users(users_db, {"id": "user1", "name": "Alice", "permissions": ["music"]})
    users.set_user_password("user1", "validpass")
    u = users.get_user_by_id("user1")
    assert users.has_password(u) is True


# ---------------------------------------------------------------------------
# Lights Out score
# ---------------------------------------------------------------------------

def test_lights_out_score_default_zero(users_db):
    seed_users(users_db, {"id": "user1", "name": "Alice", "permissions": []})
    assert users.get_lights_out_score("user1") == 0


def test_sync_lights_out_score_updates_when_local_higher(users_db):
    seed_users(users_db, {"id": "user1", "name": "Alice", "permissions": []})
    final = users.sync_lights_out_score("user1", 42)
    assert final == 42
    assert users.get_lights_out_score("user1") == 42


def test_sync_lights_out_score_keeps_server_when_higher(users_db):
    seed_users(users_db, {"id": "user1", "name": "Alice", "permissions": []})
    users.sync_lights_out_score("user1", 100)
    final = users.sync_lights_out_score("user1", 10)
    assert final == 100


# ---------------------------------------------------------------------------
# list_users
# ---------------------------------------------------------------------------

def test_list_users_sorted_by_name(users_db):
    seed_users(
        users_db,
        {"id": "2", "name": "Bob", "permissions": []},
        {"id": "1", "name": "Alice", "permissions": []},
    )
    result = users.list_users()
    assert [r["name"] for r in result] == ["Alice", "Bob"]
