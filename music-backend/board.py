import json
from datetime import datetime, timezone
from pathlib import Path

BOARD_FILE = Path("board.json")

ALLOWED_WIDGETS = {
    "now-playing": "Çalan Şarkı",
    "queue": "Kuyruk",
    "text-block": "Metin",
    "poll": "Anket",
    "cover-art": "Kapak",
}

DEFAULT_WIDGET_ORDER = [
    "now-playing",
    "queue",
    "text-block",
    "poll",
    "cover-art",
]


def _make_widget_key(widget_type, existing_keys):
    base = widget_type
    if base not in existing_keys:
        return base
    index = 2
    while f"{base}-{index}" in existing_keys:
        index += 1
    return f"{base}-{index}"


def _normalize_poll_options(options):
    rows = []
    seen = set()
    for item in options or []:
        if not isinstance(item, dict):
            continue
        option_id = item.get("id")
        label = item.get("label")
        if not isinstance(option_id, str) or not option_id.strip():
            continue
        if option_id in seen:
            continue
        clean_label = label.strip() if isinstance(label, str) else ""
        votes = item.get("votes")
        rows.append({
            "id": option_id,
            "label": clean_label or "Seçenek",
            "votes": votes if isinstance(votes, int) and votes >= 0 else 0
        })
        seen.add(option_id)
    return rows


def _default_widgets():
    widgets = []
    seen = set()
    for widget_type in DEFAULT_WIDGET_ORDER:
        key = _make_widget_key(widget_type, seen)
        entry = {
            "key": key,
            "type": widget_type,
            "title": ALLOWED_WIDGETS[widget_type],
            "pinned": False
        }
        if widget_type == "text-block":
            entry["content"] = ""
        if widget_type == "poll":
            entry["question"] = "Yeni anket"
            entry["options"] = []
        widgets.append(entry)
        seen.add(key)
    return widgets


def _normalize_widgets(raw_widgets, include_defaults=False):
    widgets = []
    seen = set()
    for item in raw_widgets or []:
        if not isinstance(item, dict):
            continue
        widget_type = item.get("type") or item.get("id")
        if widget_type not in ALLOWED_WIDGETS:
            continue
        key = item.get("key") or item.get("id")
        if not key or key in seen:
            key = _make_widget_key(widget_type, seen)
        title = item.get("title")
        clean_title = title.strip() if isinstance(title, str) else ""
        entry = {
            "key": key,
            "type": widget_type,
            "title": clean_title or ALLOWED_WIDGETS[widget_type],
            "pinned": bool(item.get("pinned"))
        }
        if widget_type == "text-block":
            content = item.get("content")
            entry["content"] = content if isinstance(content, str) else ""
        if widget_type == "poll":
            question = item.get("question")
            entry["question"] = question.strip() if isinstance(question, str) and question.strip() else "Yeni anket"
            entry["options"] = _normalize_poll_options(item.get("options"))
        widgets.append(entry)
        seen.add(key)

    if include_defaults and not widgets:
        return _default_widgets()

    return widgets


def load_board():
    if not BOARD_FILE.exists():
        data = {
            "widgets": _default_widgets(),
            "updated_by": None,
            "updated_at": None,
        }
        save_board(data)
        return data

    with open(BOARD_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    raw_widgets = data.get("widgets")
    data["widgets"] = _normalize_widgets(raw_widgets, include_defaults=raw_widgets is None)
    return data


def save_board(data):
    with open(BOARD_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def update_board(widgets=None, order_ids=None, pinned_ids=None, updated_by=None):
    data = load_board()

    if widgets is not None:
        normalized = _normalize_widgets(widgets, include_defaults=False)
        data["widgets"] = normalized
    else:
        current_widgets = _normalize_widgets(data.get("widgets"), include_defaults=True)
        by_key = {widget["key"]: widget for widget in current_widgets}

        if pinned_ids is not None:
            pinned_set = {widget_key for widget_key in pinned_ids if widget_key in by_key}
            for widget_key, widget in by_key.items():
                widget["pinned"] = widget_key in pinned_set
            pinned_order = [
                widget_key for widget_key in pinned_ids
                if widget_key in by_key and by_key[widget_key]["pinned"]
            ]
        else:
            pinned_order = [widget["key"] for widget in current_widgets if widget["pinned"]]

        if order_ids is None:
            order_ids = [widget["key"] for widget in current_widgets if not widget["pinned"]]

        unpinned_order = [
            widget_key for widget_key in order_ids
            if widget_key in by_key and not by_key[widget_key]["pinned"]
        ]

        for widget in current_widgets:
            if not widget["pinned"] and widget["key"] not in unpinned_order:
                unpinned_order.append(widget["key"])

        ordered_keys = pinned_order + unpinned_order
        data["widgets"] = [
            {
                "key": widget_key,
                "type": by_key[widget_key]["type"],
                "title": by_key[widget_key]["title"],
                "pinned": by_key[widget_key]["pinned"],
                **({"content": by_key[widget_key].get("content", "")} if by_key[widget_key]["type"] == "text-block" else {}),
                **({
                    "question": by_key[widget_key].get("question", "Yeni anket"),
                    "options": _normalize_poll_options(by_key[widget_key].get("options"))
                } if by_key[widget_key]["type"] == "poll" else {})
            }
            for widget_key in ordered_keys
        ]

    data["updated_by"] = updated_by
    data["updated_at"] = datetime.now(timezone.utc).isoformat()

    save_board(data)
    return data


def vote_poll(widget_key: str, option_id: str):
    data = load_board()
    widgets = data.get("widgets", [])
    for widget in widgets:
        if widget.get("key") == widget_key and widget.get("type") == "poll":
            options = _normalize_poll_options(widget.get("options"))
            for option in options:
                if option.get("id") == option_id:
                    option["votes"] = int(option.get("votes", 0)) + 1
                    widget["options"] = options
                    data["updated_at"] = datetime.now(timezone.utc).isoformat()
                    save_board(data)
                    return option
            break
    return None


def _sanitize_confetti_config(raw):
    if not isinstance(raw, dict):
        return {}

    def clamp(value, min_value, max_value, is_int=False):
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if number < min_value or number > max_value:
            return None
        return int(number) if is_int else number

    config = {}
    particle_count = clamp(raw.get("particleCount"), 1, 20000, is_int=True)
    if particle_count is not None:
        config["particleCount"] = particle_count

    duration_ms = clamp(raw.get("durationMs"), 1, 60000, is_int=True)
    if duration_ms is not None:
        config["durationMs"] = duration_ms

    spawn_duration_ms = clamp(raw.get("spawnDurationMs"), 0, 20000, is_int=True)
    if spawn_duration_ms is not None:
        config["spawnDurationMs"] = spawn_duration_ms

    spread = clamp(raw.get("spread"), 0.0, 10.0)
    if spread is not None:
        config["spread"] = spread

    size_scale = clamp(raw.get("sizeScale"), 0.1, 20.0)
    if size_scale is not None:
        config["sizeScale"] = size_scale

    upward_boost = clamp(raw.get("upwardBoost"), 0.0, 10.0)
    if upward_boost is not None:
        config["upwardBoost"] = upward_boost

    return config


def set_confetti_trigger(config=None, updated_by=None):
    data = load_board()
    safe_config = _sanitize_confetti_config(config or {})
    trigger_id = datetime.now(timezone.utc).isoformat()
    data["confetti_trigger"] = {
        "id": trigger_id,
        "created_at": trigger_id,
        "config": safe_config,
        "created_by": updated_by
    }
    data["updated_at"] = trigger_id
    data["updated_by"] = updated_by
    save_board(data)
    return data["confetti_trigger"]
