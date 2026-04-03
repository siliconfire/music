"""Tests for content_checker.py."""
import pytest
import content_checker as cc


CUSTOM_BLACKLIST = ["badword", "forbidden phrase", "kötü söz"]


@pytest.fixture(autouse=True)
def isolated_blacklist():
    """
    Inject a known blacklist for each test so results don't depend on
    the actual blacklists/ files on disk.
    """
    original_cache = cc._BLACKLISTS_CACHE
    original_force = cc.FORCE_ALLOW_ALL

    cc.set_force_allow_all(False)
    cc._BLACKLISTS_CACHE = list(CUSTOM_BLACKLIST)

    yield

    cc._BLACKLISTS_CACHE = original_cache
    cc.set_force_allow_all(original_force)


# ---------------------------------------------------------------------------
# Basic pass/block tests
# ---------------------------------------------------------------------------

def test_clean_text_passes():
    assert cc.content_checker("This is totally fine text") is True


def test_exact_match_blocked():
    assert cc.content_checker("contains badword here") is False


def test_exact_match_case_insensitive():
    assert cc.content_checker("BADWORD in uppercase") is False


def test_multiword_phrase_blocked():
    assert cc.content_checker("this has a forbidden phrase in it") is False


def test_unicode_phrase_blocked():
    assert cc.content_checker("kötü söz var burada") is False


def test_substring_of_bad_word_passes():
    # "badwor" is not "badword" — must not match
    assert cc.content_checker("there is badwor here", fuzzy=False) is True


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_empty_string_passes():
    assert cc.content_checker("") is True


def test_none_passes():
    assert cc.content_checker(None) is True


def test_whitespace_only_passes():
    assert cc.content_checker("   ") is True


def test_non_string_coerced_and_checked():
    # Numbers get str()-coerced; "12345" contains no bad phrase -> True
    assert cc.content_checker(12345) is True  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# force_allow_all switch
# ---------------------------------------------------------------------------

def test_force_allow_all_bypasses_blacklist():
    cc.set_force_allow_all(True)
    assert cc.content_checker("badword in here") is True


def test_force_allow_all_off_restores_blocking():
    cc.set_force_allow_all(True)
    cc.set_force_allow_all(False)
    assert cc.content_checker("badword in here") is False


# ---------------------------------------------------------------------------
# Fuzzy matching
# ---------------------------------------------------------------------------

def test_fuzzy_match_catches_typo():
    # "baadword" is close enough to "badword" to trigger fuzzy
    assert cc.content_checker("there is baadword in text", fuzzy=True) is False


def test_fuzzy_disabled_ignores_typo():
    assert cc.content_checker("there is baadword in text", fuzzy=False) is True


# ---------------------------------------------------------------------------
# find_blacklist_match helper
# ---------------------------------------------------------------------------

def test_find_blacklist_match_returns_exact_match():
    result = cc.find_blacklist_match("contains badword here", fuzzy=False)
    assert result is not None
    found, phrase, rule = result
    assert found is True
    assert phrase == "badword"
    assert rule == "Kural 1"


def test_find_blacklist_match_clean_returns_none():
    result = cc.find_blacklist_match("totally clean text", fuzzy=False)
    assert result is None


def test_find_blacklist_match_fuzzy_rule():
    result = cc.find_blacklist_match("baadword here", fuzzy=True)
    assert result is not None
    found, phrase, rule = result
    assert found is True
    assert rule == "Kural 2"


def test_find_blacklist_match_force_allow_returns_none():
    cc.set_force_allow_all(True)
    result = cc.find_blacklist_match("badword here")
    assert result is None
