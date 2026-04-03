"""Shared pytest fixtures for music-backend tests."""
import json
import sys
from pathlib import Path

# Ensure the backend package is importable regardless of where pytest is invoked.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
import users as users_mod
import board as board_mod


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def users_db(tmp_path, monkeypatch):
    """Redirect users module to an isolated temp DB file."""
    db = tmp_path / "users.json"
    monkeypatch.setattr(users_mod, "DB_FILE", db)
    return db


@pytest.fixture
def board_db(tmp_path, monkeypatch):
    """Redirect board module to an isolated temp board.json file."""
    db = tmp_path / "board.json"
    monkeypatch.setattr(board_mod, "BOARD_FILE", db)
    return db


def seed_users(db_path: Path, *specs) -> None:
    """
    Write a users DB from specs.

    Each spec is a dict with keys: id, name, permissions, banned, (optional) reason.
    """
    data: dict = {"users": {}}
    for spec in specs:
        uid = str(spec["id"])
        data["users"][uid] = {
            "name": spec.get("name", uid),
            "permissions": spec.get("permissions", []),
            "banned": spec.get("banned", False),
            "reason": spec.get("reason", None),
        }
    _write_json(db_path, data)
