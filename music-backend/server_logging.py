import json
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any

LOG_DIR = Path("logs")
LOG_FILES = {
    "requests": LOG_DIR / "requests.log",
    "song_queries": LOG_DIR / "song_queries.log",
    "song_actions": LOG_DIR / "song_actions.log",
    "board_edits": LOG_DIR / "board_edits.log",
}

# Keep logs bounded so a future frontend endpoint can tail recent entries cheaply.
DEFAULT_MAX_LINES = 20000
DEFAULT_DROP_LINES = 1000
TRIM_CHECK_EVERY = 25
MAX_TAIL_LIMIT = 500

_lock = threading.Lock()
_write_count_by_stream: dict[str, int] = {}
_policy = {
    "max_lines": DEFAULT_MAX_LINES,
    "drop_lines": DEFAULT_DROP_LINES,
}


def _ensure_dir():
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _normalize_policy(max_lines: int | None, drop_lines: int | None) -> dict[str, int]:
    max_value = int(max_lines) if isinstance(max_lines, int) else DEFAULT_MAX_LINES
    drop_value = int(drop_lines) if isinstance(drop_lines, int) else DEFAULT_DROP_LINES

    if max_value < 1000:
        max_value = 1000
    if drop_value < 1:
        drop_value = 1
    if drop_value >= max_value:
        drop_value = max(1, max_value // 2)

    return {"max_lines": max_value, "drop_lines": drop_value}


def _trim_file_if_needed(path: Path):
    try:
        if not path.exists():
            return
        with path.open("r", encoding="utf-8") as f:
            lines = f.readlines()
        max_lines = _policy["max_lines"]
        drop_lines = _policy["drop_lines"]
        while len(lines) > max_lines:
            lines = lines[drop_lines:]
        with path.open("w", encoding="utf-8") as f:
            f.writelines(lines)
    except Exception:
        # Logging should never crash the API.
        return


def _write(stream: str, payload: dict[str, Any]):
    path = LOG_FILES.get(stream)
    if path is None:
        return

    _ensure_dir()
    row = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    with _lock:
        with path.open("a", encoding="utf-8") as f:
            f.write(row + "\n")

        count = _write_count_by_stream.get(stream, 0) + 1
        _write_count_by_stream[stream] = count
        if count % TRIM_CHECK_EVERY == 0:
            _trim_file_if_needed(path)


def emit(stream: str, event: str, **meta: Any):
    payload = {"ts": _now_iso(), "event": event, **meta}
    _write(stream, payload)


def log_request(**meta: Any):
    emit("requests", "request", **meta)


def log_song_query(**meta: Any):
    emit("song_queries", "song_query", **meta)


def log_song_action(action: str, **meta: Any):
    emit("song_actions", action, **meta)


def log_board_edit(action: str, **meta: Any):
    emit("board_edits", action, **meta)


def list_streams() -> list[str]:
    return sorted(LOG_FILES.keys())


def get_policy() -> dict[str, int]:
    with _lock:
        return dict(_policy)


def set_policy(max_lines: int | None = None, drop_lines: int | None = None) -> dict[str, int]:
    with _lock:
        normalized = _normalize_policy(max_lines=max_lines, drop_lines=drop_lines)
        _policy.update(normalized)
        return dict(_policy)


def clear_stream(stream: str) -> bool:
    if stream not in LOG_FILES:
        raise ValueError("Unknown log stream")
    path = LOG_FILES[stream]
    _ensure_dir()
    with _lock:
        with path.open("w", encoding="utf-8") as f:
            f.write("")
    return True


def _normalize_limit(limit: int | None) -> int:
    if not isinstance(limit, int):
        return 100
    if limit < 1:
        return 1
    if limit > MAX_TAIL_LIMIT:
        return MAX_TAIL_LIMIT
    return limit


def tail_stream(stream: str, limit: int | None = 100) -> dict[str, Any]:
    if stream not in LOG_FILES:
        raise ValueError("Unknown log stream")

    normalized_limit = _normalize_limit(limit)
    path = LOG_FILES[stream]
    if not path.exists():
        return {
            "stream": stream,
            "limit": normalized_limit,
            "exists": False,
            "total_entries": 0,
            "entries": [],
            "parse_warnings": 0,
        }

    rows = deque(maxlen=normalized_limit)
    total_entries = 0
    with _lock:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                clean = line.rstrip("\r\n")
                if clean:
                    total_entries += 1
                    rows.append(clean)

    entries: list[dict[str, Any]] = []
    parse_warnings = 0
    for row in rows:
        try:
            parsed = json.loads(row)
            if isinstance(parsed, dict):
                entries.append(parsed)
            else:
                parse_warnings += 1
                entries.append({"raw": row})
        except Exception:
            parse_warnings += 1
            entries.append({"raw": row})

    return {
        "stream": stream,
        "limit": normalized_limit,
        "exists": True,
        "total_entries": total_entries,
        "entries": entries,
        "parse_warnings": parse_warnings,
    }


