"""
Simple content checker for the music-backend.

Function: content_checker(text: str, ai=None) -> bool
- Returns True when the provided text is appropriate (no blacklist matches).
- Returns False when any blacklisted phrase is found (case-insensitive substring match).

Blacklists are read from the `blacklists/` directory next to this file. Any `*.txt` file placed there
will be read; each non-empty line (stripped) is treated as one blacklist entry. Lines starting with
`#` are ignored so you can add comments.

This module caches the loaded blacklist entries on import. Call `reload_blacklists()` to refresh.
"""
from __future__ import annotations

from pathlib import Path
from typing import List
import difflib
import unicodedata
import os

# Master switch: when True, all content is treated as safe and no blacklist matches are reported.
# Can be toggled at runtime via set_force_allow_all() or set with the CONTENT_CHECK_FORCE_ALLOW_ALL env var.
FORCE_ALLOW_ALL = os.getenv("CONTENT_CHECK_FORCE_ALLOW_ALL", "false").lower() in ("1", "true", "yes", "y")


def set_force_allow_all(value: bool):
    """Set the runtime master switch for allowing all content.

    Usage:
    - At runtime: import content_checker; content_checker.set_force_allow_all(True)
    - Or set environment variable CONTENT_CHECK_FORCE_ALLOW_ALL=true before starting the app.
    """
    global FORCE_ALLOW_ALL
    FORCE_ALLOW_ALL = bool(value)


# Cache for blacklist phrases (lowercased)
_BLACKLISTS_CACHE: List[str] | None = None


def _blacklists_dir() -> Path:
    """Return the Path to the blacklists directory next to this file."""
    return Path(__file__).resolve().parent / "blacklists"


def _normalize(s: str) -> str:
    """Apply unicode normalization and lowercase for consistent comparisons."""
    if not isinstance(s, str):
        return ""
    return unicodedata.normalize("NFKC", s).lower()


def _load_blacklists() -> List[str]:
    """Read all .txt files in the blacklists directory and return a list of phrases (lowercased).

    Rules:
    - Ignore empty lines and lines starting with '#'
    - Strip whitespace
    - Treat each line as a literal substring to search for (case-insensitive)
    """
    folder = _blacklists_dir()
    phrases: List[str] = []

    if not folder.exists():
        return []

    for path in sorted(folder.glob("*.txt")):
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            # if file is unreadable, move on
            continue

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            phrases.append(_normalize(line))

    return phrases


def reload_blacklists() -> None:
    """Force reload of blacklist phrases from disk into the module cache."""
    global _BLACKLISTS_CACHE
    _BLACKLISTS_CACHE = _load_blacklists()


def _get_blacklist_phrases() -> List[str]:
    """Return cached blacklist phrases, loading them if necessary."""
    global _BLACKLISTS_CACHE
    if _BLACKLISTS_CACHE is None:
        _BLACKLISTS_CACHE = _load_blacklists()
    return _BLACKLISTS_CACHE


def _fuzzy_contains(text: str, phrase: str, threshold: float = 0.80) -> bool:
    """Return True if `phrase` approximately appears in `text` using a sliding window and
    difflib.SequenceMatcher ratio.

    Notes:
    - Very short phrases (length < 4) are not fuzzy-matched to avoid noisy false positives.
    - Both `text` and `phrase` should already be normalized/lowercased by the caller.
    """
    if not phrase:
        return False
    # avoid fuzzy matching for very short phrases
    if len(phrase) < 4:
        return False

    # Collapse whitespace in text and phrase to make matches more robust
    t = " ".join(text.split())
    p = " ".join(phrase.split())
    plen = len(p)
    tlen = len(t)
    if tlen == 0 or plen == 0 or plen > tlen * 2:
        # nothing to compare or phrase ridiculously larger than text
        return False

    # try windows around phrase length (exact length and +/- 2)
    for win_len in {plen, max(1, plen - 2), plen + 2}:
        if win_len > tlen:
            continue
        for i in range(0, tlen - win_len + 1):
            window = t[i:i + win_len]
            r = difflib.SequenceMatcher(None, p, window).ratio()
            if r >= threshold:
                return True

    return False


def content_checker(text: str, ai=None, fuzzy: bool = True) -> bool:
    """Return True if `text` is appropriate (no blacklist phrase present), False otherwise.

    Parameters:
    - text: the content string to check
    - ai: optional parameter reserved for future use (ignored currently)
    - fuzzy: when True (default), perform fuzzy substring matching in addition to exact checks

    Behavior:
    - Loads all blacklist phrases (from `blacklists/*.txt` next to this module)
    - Performs case-insensitive substring matching: if any blacklist phrase appears anywhere in
      `text` (after normalizing), the function returns False. When `fuzzy` is True, also performs
      an approximate match using difflib for phrases of length >= 4.
    """
    # Fast-path master switch: if enabled, treat everything as safe
    if FORCE_ALLOW_ALL:
        return True

    if text is None:
        # Treat None as empty/appropriate
        return True

    lower_text = _normalize(str(text))
    for phrase in _get_blacklist_phrases():
        if not phrase:
            continue
        # exact substring match (fast path)
        if phrase in lower_text:
            return False
        # fuzzy check
        if fuzzy and _fuzzy_contains(lower_text, phrase):
            return False

    return True


def find_blacklist_match(text: str, fuzzy: bool = True) -> tuple[bool, str, str] | None:
    # If master switch on, always act as if there is no match
    if FORCE_ALLOW_ALL:
        return None

    if text is None:
        # return a 3-tuple consistent with the function's annotated return type
        return False, "-", ""

    lower_text = _normalize(str(text))
    for phrase in _get_blacklist_phrases():
        if not phrase:
            continue
        if phrase in lower_text:
            return True, phrase, "Kural 1"
        if fuzzy and _fuzzy_contains(lower_text, phrase):
            return True, phrase, "Kural 2"
    return None
