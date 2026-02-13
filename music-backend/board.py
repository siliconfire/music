import json
from datetime import datetime, timezone
from pathlib import Path

BOARD_FILE = Path("board.json")

ALLOWED_WIDGETS = {
    "now-playing": "Çalan Şarkı",
    "queue": "Kuyruk",
    "text-block": "Metin",
    "poll": "Anket",
    "clock": "Saat",
    "controls": "Kontroller",
}

DEFAULT_WIDGET_ORDER = [
    "now-playing",
    "queue",
    "text-block",
    "poll",
]

DEFAULT_THEME_KEY = "classic"
THEME_PRESETS = {
    "classic": {
        "key": "classic",
        "label": "Klasik",
        "colors": {
            "textPrimary": "#0f172a",
            "textSecondary": "#475569",
            "background": "#f8fafc",
            "cardBackground": "#ffffff",
            "cardBorder": "#cbd5f5",
            "cardPinnedBackground": "#ecfdf5",
            "cardPinnedBorder": "#6ee7b7",
            "qrButtonBackground": "#ffffff",
            "qrButtonBorder": "#cbd5f5",
            "qrButtonText": "#0f172a",
            "confettiColors": ["#22c55e", "#16a34a", "#a3e635", "#86efac", "#4ade80", "#10b981"]
        }
    },
    "midnight": {
        "key": "midnight",
        "label": "Akşam Saati",
        "colors": {
            "textPrimary": "#e2e8f0",
            "textSecondary": "#94a3b8",
            "background": "#0b1120",
            "cardBackground": "#111827",
            "cardBorder": "#334155",
            "cardPinnedBackground": "#0f172a",
            "cardPinnedBorder": "#64748b",
            "qrButtonBackground": "#111827",
            "qrButtonBorder": "#334155",
            "qrButtonText": "#e2e8f0",
            "confettiColors": ["#38bdf8", "#818cf8", "#f472b6", "#facc15", "#34d399", "#22d3ee"]
        }
    },
    "sunset": {
        "key": "sunset",
        "label": "\"Bal\" Gibi",
        "colors": {
            "textPrimary": "#3f1d2e",
            "textSecondary": "#7c2d12",
            "background": "#fff7ed",
            "cardBackground": "#fffaf5",
            "cardBorder": "#fdba74",
            "cardPinnedBackground": "#ffedd5",
            "cardPinnedBorder": "#fb923c",
            "qrButtonBackground": "#fff7ed",
            "qrButtonBorder": "#fdba74",
            "qrButtonText": "#7c2d12",
            "confettiColors": ["#f97316", "#fb7185", "#f59e0b", "#facc15", "#fb923c", "#fdba74"]
        }
    },
    "nordic": {
        "key": "nordic",
        "label": "Bartın'a kar yağmış",
        "colors": {
            "textPrimary": "#1e293b",
            "textSecondary": "#64748b",
            "background": "#f1f5f9",
            "cardBackground": "#ffffff",
            "cardBorder": "#e2e8f0",
            "cardPinnedBackground": "#f0f9ff",
            "cardPinnedBorder": "#7dd3fc",
            "qrButtonBackground": "#ffffff",
            "qrButtonBorder": "#e2e8f0",
            "qrButtonText": "#0369a1",
            "confettiColors": ["#0ea5e9", "#38bdf8", "#7dd3fc", "#bae6fd", "#e0f2fe", "#0284c7"]
        }
    },
    "cyberpunk": {
        "key": "cyberpunk",
        "label": "Geleceksel",
        "colors": {
            "textPrimary": "#fdf4ff",
            "textSecondary": "#d8b4fe",
            "background": "#020617",
            "cardBackground": "#0f172a",
            "cardBorder": "#581c87",
            "cardPinnedBackground": "#2e1065",
            "cardPinnedBorder": "#d946ef",
            "qrButtonBackground": "#1e1b4b",
            "qrButtonBorder": "#d946ef",
            "qrButtonText": "#fdf4ff",
            "confettiColors": ["#d946ef", "#8b5cf6", "#06b6d4", "#f472b6", "#22d3ee", "#a855f7"]
        }
    },
    "rose": {
        "key": "rose",
        "label": "Bubble Tea",
        "colors": {
            "textPrimary": "#4c0519",
            "textSecondary": "#881337",
            "background": "#fff1f2",
            "cardBackground": "#fffafb",
            "cardBorder": "#fecdd3",
            "cardPinnedBackground": "#ffe4e6",
            "cardPinnedBorder": "#fb7185",
            "qrButtonBackground": "#ffffff",
            "qrButtonBorder": "#fecdd3",
            "qrButtonText": "#be123c",
            "confettiColors": ["#fb7185", "#f43f5e", "#fda4af", "#e11d48", "#fbcfe8", "#db2777"]
        }
    },
    "telegram_pink": {
        "key": "telegram_pink",
        "label": "Gerçek Telegram Pembesi",
        "colors": {
            "textPrimary": "#ffffff",
            "textSecondary": "#aaaaaa",
            "background": "#18222d",
            "cardBackground": "#242f3d",
            "cardBorder": "#323d4d",
            "cardPinnedBackground": "#2b394a",
            "cardPinnedBorder": "#ee6aa7",
            "qrButtonBackground": "#242f3d",
            "qrButtonBorder": "#ee6aa7",
            "qrButtonText": "#ee6aa7",
            "confettiColors": ["#ee6aa7", "#f9a8d4", "#f472b6", "#db2777", "#9d174d", "#fdf2f8"]
        }
    },
    "telegram_pink2": {
        "key": "telegram_pink2",
        "label": "Daha Gerçek Telegram Pembesi",
        "colors": {
            "textPrimary": "#ffffff",
            "textSecondary": "#94a3b8",
            "background": "#1c1215",
            "cardBackground": "#281a1e",
            "cardBorder": "#3d262c",
            "cardPinnedBackground": "#4c1d24",
            "cardPinnedBorder": "#f472b6",
            "qrButtonBackground": "#281a1e",
            "qrButtonBorder": "#f472b6",
            "qrButtonText": "#f472b6",
            "confettiColors": ["#f472b6", "#be185d", "#9d174d", "#ec4899", "#701a75", "#f9a8d4"]
        }
    },
    "hacker_dark": {
        "key": "hacker_dark",
        "label": "Hacker",
        "colors": {
            "textPrimary": "#00ff41",
            "textSecondary": "#008f11",
            "background": "#050f05",
            "cardBackground": "#000000",
            "cardBorder": "#003b00",
            "cardPinnedBackground": "#001100",
            "cardPinnedBorder": "#00ff41",
            "qrButtonBackground": "#003b00",
            "qrButtonBorder": "#008f11",
            "qrButtonText": "#00ff41",
            "confettiColors": ["#00ff41", "#008f11", "#003b00", "#0d0208", "#00FF00", "#125512"]
        }
    },
    "gruvbox_dark": {
        "key": "gruvbox_dark",
        "label": "Lidya Sarısı",
        "colors": {
            "textPrimary": "#ebdbb2",
            "textSecondary": "#a89984",
            "background": "#1d2021",
            "cardBackground": "#282828",
            "cardBorder": "#3c3836",
            "cardPinnedBackground": "#32302f",
            "cardPinnedBorder": "#fabd2f",
            "qrButtonBackground": "#3c3836",
            "qrButtonBorder": "#504945",
            "qrButtonText": "#fabd2f",
            "confettiColors": ["#fb4934", "#b8bb26", "#fabd2f", "#83a598", "#d3869b", "#8ec07c"]
        }
    },
    "deep_forest": {
        "key": "deep_forest",
        "label": "Yeşil Madde",
        "colors": {
            "textPrimary": "#ecfdf5",
            "textSecondary": "#a7f3d0",
            "background": "#061612",
            "cardBackground": "#0c221d",
            "cardBorder": "#164e41",
            "cardPinnedBackground": "#14532d",
            "cardPinnedBorder": "#4ade80",
            "qrButtonBackground": "#0c221d",
            "qrButtonBorder": "#164e41",
            "qrButtonText": "#4ade80",
            "confettiColors": ["#065f46", "#059669", "#10b981", "#34d399", "#6ee7b7", "#a7f3d0"]
        }
    },
    "black_eclipse": {
        "key": "black_eclipse",
        "label": "Siyahın Asaleti",
        "colors": {
            "textPrimary": "#ffffff",
            "textSecondary": "#94a3b8",
            "background": "#000000",
            "cardBackground": "#0a0a0a",
            "cardBorder": "#262626",
            "cardPinnedBackground": "#171717",
            "cardPinnedBorder": "#facc15",
            "qrButtonBackground": "#000000",
            "qrButtonBorder": "#404040",
            "qrButtonText": "#ffffff",
            "confettiColors": ["#ffffff", "#facc15", "#e5e5e5", "#a3a3a3", "#fbbf24", "#d4d4d4"]
        }
    },
    "deep_ocean": {
        "key": "deep_ocean",
        "label": "Zoktay Mavisi",
        "colors": {
            "textPrimary": "#f0f9ff",
            "textSecondary": "#7dd3fc",
            "background": "#020617",
            "cardBackground": "#0f172a",
            "cardBorder": "#1e3a8a",
            "cardPinnedBackground": "#172554",
            "cardPinnedBorder": "#38bdf8",
            "qrButtonBackground": "#0f172a",
            "qrButtonBorder": "#38bdf8",
            "qrButtonText": "#38bdf8",
            "confettiColors": ["#0ea5e9", "#2563eb", "#06b6d4", "#7dd3fc", "#1d4ed8", "#67e8f9"]
        }
    }
}


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
        if widget_type == "clock":
            show_date = item.get("show_date")
            show_seconds = item.get("show_seconds")
            entry["show_date"] = show_date if isinstance(show_date, bool) else True
            entry["show_seconds"] = show_seconds if isinstance(show_seconds, bool) else False
        if widget_type == "controls":
            entry["show_confetti"] = bool(item.get("show_confetti", True))
            entry["show_theme"] = bool(item.get("show_theme", True))
            entry["show_reload"] = bool(item.get("show_reload", False))
            entry["display_text"] = bool(item.get("display_text", True))
        widgets.append(entry)
        seen.add(key)

    if include_defaults and not widgets:
        return _default_widgets()

    return widgets


def _normalize_theme_key(value):
    if isinstance(value, str) and value in THEME_PRESETS:
        return value
    return DEFAULT_THEME_KEY


def _theme_payload(theme_key):
    preset = THEME_PRESETS.get(theme_key) or THEME_PRESETS[DEFAULT_THEME_KEY]
    return {
        "key": preset["key"],
        "label": preset["label"],
        "colors": preset["colors"]
    }


def _theme_presets_payload():
    return [
        {
            "key": preset["key"],
            "label": preset["label"],
            "colors": preset["colors"]
        }
        for preset in THEME_PRESETS.values()
    ]


def load_board():
    if not BOARD_FILE.exists():
        data = {
            "widgets": _default_widgets(),
            "updated_by": None,
            "updated_at": None,
            "debug_passkeys": [],
            "theme_key": DEFAULT_THEME_KEY
        }
        save_board(data)
        return data

    with open(BOARD_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    raw_widgets = data.get("widgets")
    data["widgets"] = _normalize_widgets(raw_widgets, include_defaults=raw_widgets is None)
    data["debug_passkeys"] = _normalize_passkeys(data.get("debug_passkeys"))
    theme_key = _normalize_theme_key(data.get("theme_key"))
    data["theme_key"] = theme_key
    data["theme"] = _theme_payload(theme_key)
    data["theme_presets"] = _theme_presets_payload()
    return data


def save_board(data):
    with open(BOARD_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def update_board(widgets=None, order_ids=None, pinned_ids=None, updated_by=None, theme_key=None):
    data = load_board()

    if widgets is not None:
        normalized = _normalize_widgets(widgets, include_defaults=False)
        current_widgets = _normalize_widgets(data.get("widgets"), include_defaults=True)
        current_polls = {
            widget.get("key"): {
                option.get("id"): option.get("votes", 0)
                for option in widget.get("options", [])
                if isinstance(option, dict)
            }
            for widget in current_widgets
            if widget.get("type") == "poll"
        }
        for widget in normalized:
            if widget.get("type") != "poll":
                continue
            existing_votes = current_polls.get(widget.get("key"), {})
            for option in widget.get("options", []) or []:
                option_id = option.get("id")
                if option_id in existing_votes:
                    option["votes"] = existing_votes[option_id]
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
                } if by_key[widget_key]["type"] == "poll" else {}),
                **({
                    "show_date": by_key[widget_key].get("show_date", True),
                    "show_seconds": bool(by_key[widget_key].get("show_seconds", False))
                } if by_key[widget_key]["type"] == "clock" else {}),
                **({
                    "show_confetti": bool(by_key[widget_key].get("show_confetti", True)),
                    "show_theme": bool(by_key[widget_key].get("show_theme", True)),
                    "show_reload": bool(by_key[widget_key].get("show_reload", False)),
                    "display_text": bool(by_key[widget_key].get("display_text", True)),
                } if by_key[widget_key]["type"] == "controls" else {}),
            }
            for widget_key in ordered_keys
        ]

    if theme_key is not None:
        data["theme_key"] = _normalize_theme_key(theme_key)

    data["theme"] = _theme_payload(data.get("theme_key"))
    data["theme_presets"] = _theme_presets_payload()
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


def set_restart_trigger(updated_by=None):
    data = load_board()
    trigger_id = datetime.now(timezone.utc).isoformat()
    data["restart_trigger"] = {
        "id": trigger_id,
        "created_at": trigger_id,
        "created_by": updated_by
    }
    data["updated_at"] = trigger_id
    data["updated_by"] = updated_by
    save_board(data)
    return data["restart_trigger"]


def _normalize_passkeys(raw):
    if not isinstance(raw, list):
        return []
    seen = set()
    result = []
    for item in raw:
        if not isinstance(item, str):
            continue
        cleaned = item.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def get_debug_passkeys():
    data = load_board()
    return _normalize_passkeys(data.get("debug_passkeys"))


def update_debug_passkeys(passkeys):
    data = load_board()
    data["debug_passkeys"] = _normalize_passkeys(passkeys)
    save_board(data)
    return data["debug_passkeys"]
