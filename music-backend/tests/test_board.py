"""Tests for board.py."""
import json
import pytest

import board
from board import (
    ALLOWED_WIDGETS,
    DEFAULT_THEME_KEY,
    THEME_PRESETS,
    load_board,
    update_board,
    vote_poll,
    set_confetti_trigger,
    set_restart_trigger,
    set_redirect_trigger,
    _normalize_backdrop_blur_px,
    _normalize_card_blur_px,
    _normalize_conway_trigger_mode,
    _normalize_theme_key,
)


# ---------------------------------------------------------------------------
# load_board — default state
# ---------------------------------------------------------------------------

def test_load_board_creates_defaults_when_file_missing(board_db):
    data = load_board()
    assert "widgets" in data
    assert isinstance(data["widgets"], list)
    assert len(data["widgets"]) > 0
    assert data["theme_key"] == DEFAULT_THEME_KEY


def test_load_board_creates_file_on_disk(board_db):
    load_board()
    assert board_db.exists()


def test_load_board_default_widgets_are_known_types(board_db):
    data = load_board()
    for widget in data["widgets"]:
        assert widget["type"] in ALLOWED_WIDGETS


def test_load_board_includes_theme_and_presets(board_db):
    load_board()  # creates the file
    data = load_board()  # second call reads from disk and adds theme/theme_presets
    assert "theme" in data
    assert "theme_presets" in data
    assert isinstance(data["theme_presets"], list)
    assert len(data["theme_presets"]) == len(THEME_PRESETS)


def test_load_board_default_blur_values(board_db):
    data = load_board()
    assert data["backdrop_blur_px"] == 0
    assert data["card_blur_px"] == 12


# ---------------------------------------------------------------------------
# update_board — theme
# ---------------------------------------------------------------------------

def test_update_board_changes_theme(board_db):
    load_board()
    data = update_board(theme_key="midnight")
    assert data["theme_key"] == "midnight"
    assert data["theme"]["key"] == "midnight"


def test_update_board_unknown_theme_falls_back_to_default(board_db):
    load_board()
    data = update_board(theme_key="nonexistent_theme")
    assert data["theme_key"] == DEFAULT_THEME_KEY


def test_update_board_persists_theme(board_db):
    load_board()
    update_board(theme_key="sunset")
    reloaded = load_board()
    assert reloaded["theme_key"] == "sunset"


# ---------------------------------------------------------------------------
# update_board — blur
# ---------------------------------------------------------------------------

def test_update_board_backdrop_blur(board_db):
    load_board()
    data = update_board(backdrop_blur_px=20)
    assert data["backdrop_blur_px"] == 20


def test_update_board_blur_clamped_to_max(board_db):
    load_board()
    data = update_board(backdrop_blur_px=999)
    assert data["backdrop_blur_px"] == 40


def test_update_board_card_blur_clamped(board_db):
    load_board()
    data = update_board(card_blur_px=50)
    assert data["card_blur_px"] == 30


def test_update_board_blur_below_zero_clamped(board_db):
    load_board()
    data = update_board(backdrop_blur_px=-5)
    assert data["backdrop_blur_px"] == 0


# ---------------------------------------------------------------------------
# update_board — widgets
# ---------------------------------------------------------------------------

def test_update_board_set_widgets(board_db):
    load_board()
    new_widgets = [
        {"type": "now-playing", "key": "now-playing", "title": "Now Playing", "pinned": False},
        {"type": "clock", "key": "clock", "title": "Clock", "pinned": False,
         "show_date": True, "show_seconds": False},
    ]
    data = update_board(widgets=new_widgets)
    types = [w["type"] for w in data["widgets"]]
    assert "now-playing" in types
    assert "clock" in types


def test_update_board_widgets_invalid_type_ignored(board_db):
    load_board()
    new_widgets = [
        {"type": "now-playing", "key": "now-playing", "title": "NP", "pinned": False},
        {"type": "invalid-widget", "key": "bad", "title": "Bad", "pinned": False},
    ]
    data = update_board(widgets=new_widgets)
    types = [w["type"] for w in data["widgets"]]
    assert "invalid-widget" not in types


def test_update_board_updated_at_set(board_db):
    load_board()
    data = update_board(theme_key="midnight", updated_by="testuser")
    assert data["updated_by"] == "testuser"
    assert data["updated_at"] is not None


# ---------------------------------------------------------------------------
# vote_poll
# ---------------------------------------------------------------------------

def test_vote_poll_increments_count(board_db):
    load_board()
    poll_widget = {
        "type": "poll",
        "key": "poll",
        "title": "Poll",
        "pinned": False,
        "question": "Best color?",
        "options": [
            {"id": "opt1", "label": "Red", "votes": 0},
            {"id": "opt2", "label": "Blue", "votes": 0},
        ],
    }
    update_board(widgets=[poll_widget])
    result = vote_poll("poll", "opt1")
    assert result is not None
    assert result["votes"] == 1


def test_vote_poll_multiple_times(board_db):
    load_board()
    poll_widget = {
        "type": "poll",
        "key": "poll",
        "title": "Poll",
        "pinned": False,
        "question": "Best color?",
        "options": [{"id": "opt1", "label": "Red", "votes": 5}],
    }
    update_board(widgets=[poll_widget])
    vote_poll("poll", "opt1")
    result = vote_poll("poll", "opt1")
    assert result["votes"] == 7


def test_vote_poll_unknown_widget_returns_none(board_db):
    load_board()
    result = vote_poll("nonexistent", "opt1")
    assert result is None


def test_vote_poll_unknown_option_returns_none(board_db):
    load_board()
    poll_widget = {
        "type": "poll",
        "key": "poll",
        "title": "Poll",
        "pinned": False,
        "question": "Q?",
        "options": [{"id": "opt1", "label": "A", "votes": 0}],
    }
    update_board(widgets=[poll_widget])
    result = vote_poll("poll", "nonexistent_option")
    assert result is None


# ---------------------------------------------------------------------------
# set_confetti_trigger / set_restart_trigger / set_redirect_trigger
# ---------------------------------------------------------------------------

def test_set_confetti_trigger_returns_trigger(board_db):
    load_board()
    result = set_confetti_trigger(config={"particleCount": 100}, updated_by="admin")
    assert result["id"] is not None
    assert result["created_by"] == "admin"


def test_set_restart_trigger(board_db):
    load_board()
    result = set_restart_trigger(updated_by="admin")
    assert result["id"] is not None


def test_set_redirect_trigger_valid_path(board_db):
    load_board()
    result = set_redirect_trigger(path="/board", updated_by="admin")
    assert result["path"] == "/board"


def test_set_redirect_trigger_rejects_http(board_db):
    load_board()
    result = set_redirect_trigger(path="http://evil.com", updated_by="admin")
    assert result["path"] is None


# ---------------------------------------------------------------------------
# _normalize_* helpers (pure functions, no DB needed)
# ---------------------------------------------------------------------------

def test_normalize_backdrop_blur_px_clamp():
    assert _normalize_backdrop_blur_px(0) == 0
    assert _normalize_backdrop_blur_px(40) == 40
    assert _normalize_backdrop_blur_px(41) == 40
    assert _normalize_backdrop_blur_px(-1) == 0
    assert _normalize_backdrop_blur_px(None) == 0


def test_normalize_card_blur_px_clamp():
    assert _normalize_card_blur_px(0) == 0
    assert _normalize_card_blur_px(30) == 30
    assert _normalize_card_blur_px(31) == 30
    assert _normalize_card_blur_px(None) == 12  # default


def test_normalize_conway_trigger_mode_valid():
    assert _normalize_conway_trigger_mode("click") == "click"
    assert _normalize_conway_trigger_mode("hover") == "hover"


def test_normalize_conway_trigger_mode_invalid():
    assert _normalize_conway_trigger_mode("double-click") == "click"  # default
    assert _normalize_conway_trigger_mode(None) == "click"


def test_normalize_theme_key_valid():
    assert _normalize_theme_key("midnight") == "midnight"
    assert _normalize_theme_key("sunset") == "sunset"


def test_normalize_theme_key_invalid_returns_default():
    assert _normalize_theme_key("nonexistent") == DEFAULT_THEME_KEY
    assert _normalize_theme_key(None) == DEFAULT_THEME_KEY
