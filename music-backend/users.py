import json
from pathlib import Path

from fastapi import HTTPException

DB_FILE = Path("users.json")

# Define ranks in ascending order (lowest -> highest)
RANKS = [
    "music",
    "musicpermanent",
    "moderator",
    "admin",
    "superadmin",
    "dev",
]


def load_db():
    if not DB_FILE.exists():
        return {"users": {}}
    with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)         # indent=4 makes it manaully editable



def get_user(user_id: str):
    db = load_db()
    return db["users"].get(str(user_id))


def get_user_by_id(user_id: str):
    if not DB_FILE.exists():
        return None

    with open(DB_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    # JSON keys are always strings, so we cast user_id to strv
    return data.get("users", {}).get(str(user_id))


def list_users():
    db = load_db()
    users = db.get("users", {})
    rows = []
    for user_id, user in users.items():
        rows.append({
            "id": str(user_id),
            "name": user.get("name"),
            "permissions": user.get("permissions", []),
            "banned": user.get("banned", False),
            "reason": user.get("reason"),
            "has_password": has_password(user)
        })
    rows.sort(key=lambda row: row.get("name") or row.get("id"))
    return rows


def _normalize_passkeys(passkeys):
    if not isinstance(passkeys, list):
        return []
    seen = set()
    rows = []
    for item in passkeys:
        if not isinstance(item, dict):
            continue
        cred_id = item.get("id")
        public_key = item.get("public_key") or item.get("publicKey")
        if not isinstance(cred_id, str) or not cred_id.strip():
            continue
        if not isinstance(public_key, str) or not public_key.strip():
            continue
        if cred_id in seen:
            continue
        rows.append({
            "id": cred_id.strip(),
            "public_key": public_key.strip(),
            "sign_count": int(item.get("sign_count", 0)) if str(item.get("sign_count", "")).isdigit() else 0
        })
        seen.add(cred_id)
    return rows


def get_user_passkeys(user: dict | None):
    if not user:
        return []
    return _normalize_passkeys(user.get("passkeys"))


def get_passkey_users_public():
    db = load_db()
    users = db.get("users", {})
    rows = []
    for user_id, user in users.items():
        passkeys = get_user_passkeys(user)
        if not passkeys:
            continue
        rows.append({
            "id": str(user_id),
            "name": user.get("name"),
            "permissions": user.get("permissions", []),
            "banned": user.get("banned", False),
            "passkeys": passkeys
        })
    rows.sort(key=lambda row: row.get("name") or row.get("id"))
    return rows


def add_user_passkey(user_id: str, credential_id: str, public_key: str, sign_count: int = 0):
    db = load_db()
    user = db.get("users", {}).get(str(user_id))
    if not user:
        return None
    passkeys = get_user_passkeys(user)
    for entry in passkeys:
        if entry.get("id") == credential_id:
            return entry
    entry = {
        "id": credential_id,
        "public_key": public_key,
        "sign_count": int(sign_count) if isinstance(sign_count, int) and sign_count >= 0 else 0,
        "created_at": user.get("passkey_created_at") or None
    }
    passkeys.append(entry)
    user["passkeys"] = passkeys
    save_db(db)
    return entry


def remove_user_passkey(user_id: str, credential_id: str):
    db = load_db()
    user = db.get("users", {}).get(str(user_id))
    if not user:
        return False
    passkeys = get_user_passkeys(user)
    next_passkeys = [entry for entry in passkeys if entry.get("id") != credential_id]
    if len(next_passkeys) == len(passkeys):
        return False
    user["passkeys"] = next_passkeys
    save_db(db)
    return True


def find_user_by_passkey_id(credential_id: str):
    db = load_db()
    users = db.get("users", {})
    for user_id, user in users.items():
        for entry in get_user_passkeys(user):
            if entry.get("id") == credential_id:
                return str(user_id), user, entry
    return None, None, None


def update_passkey_sign_count(user_id: str, credential_id: str, new_count: int):
    db = load_db()
    user = db.get("users", {}).get(str(user_id))
    if not user:
        return False
    passkeys = get_user_passkeys(user)
    updated = False
    for entry in passkeys:
        if entry.get("id") == credential_id:
            entry["sign_count"] = int(new_count) if isinstance(new_count, int) and new_count >= 0 else 0
            updated = True
            break
    if not updated:
        return False
    user["passkeys"] = passkeys
    save_db(db)
    return True


def check_user_perm(user_id: str, required_perm: str) -> bool:
    user = get_user_by_id(user_id)

    if not user or user.get("banned"):
        return False

    return required_perm in user.get("permissions", [])


def check_user_rank_or_higher(user_id: str, required_perm: str) -> bool:
    user = get_user_by_id(user_id)
    if not user or user.get("banned"):
        return False

    if required_perm not in RANKS:
        return required_perm in user.get("permissions", [])

    return highest_rank_index(user) >= _rank_index(required_perm)


def check_user_rank_above(user_id: str, required_perm: str) -> bool:
    user = get_user_by_id(user_id)
    if not user or user.get("banned"):
        return False
    if required_perm not in RANKS:
        return required_perm in user.get("permissions", [])
    return highest_rank_index(user) > _rank_index(required_perm)


# --- Permission management helpers ---

def _rank_index(permission: str) -> int:
    """Return the rank index (higher is more powerful). Returns -1 if not a known rank."""
    try:
        return RANKS.index(permission)
    except ValueError:
        return -1


def highest_rank_index(user: dict) -> int:
    """Return the highest rank index a user currently has. -1 if none."""
    perms = user.get("permissions", []) if user else []
    highest = -1
    for p in perms:
        idx = _rank_index(p)
        if idx > highest:
            highest = idx
    return highest


def add_permission(actor_id: str, target_id: str, permission: str):
    """Add a permission to target user if actor is allowed.

    Rules enforced:
    - permission must be one of the known RANKS.
    - actor must exist and must not be banned.
    - actor must have at least the 'admin' level (i.e. highest rank index >= index('admin')).
    - actor's highest rank index must be strictly greater than the rank index of the permission being added.

    Returns the updated target user dict on success. Raises HTTPException on errors.
    """
    perm_idx = _rank_index(permission)
    if perm_idx == -1:
        raise HTTPException(status_code=400, detail=f"Unknown permission: {permission}")

    actor = get_user_by_id(actor_id)
    if not actor:
        raise HTTPException(status_code=404, detail="Actor user not found")
    if actor.get("banned"):
        raise HTTPException(status_code=403, detail="Actor is banned")

    actor_highest = highest_rank_index(actor)
    admin_idx = _rank_index("admin")

    # Minimum required: actor must have at least 'admin' level
    if actor_highest < admin_idx:
        raise HTTPException(status_code=403, detail="You don't have permission to modify roles (requires admin or higher).")

    # Actor must be strictly higher than the permission they're trying to add
    if actor_highest <= perm_idx:
        raise HTTPException(status_code=403, detail="You can't grant a role equal or higher than your own highest role.")

    # Load DB and target user
    db = load_db()
    users = db.setdefault("users", {})
    target = users.get(str(target_id))
    if not target:
        raise HTTPException(status_code=404, detail="Target user not found")

    perms = set(target.get("permissions", []))
    if permission in perms:
        # No-op
        return target

    perms.add(permission)
    # maintain order roughly according to RANKS when saving
    ordered = [p for p in RANKS if p in perms]
    # include any custom permissions (not in RANKS) at end
    ordered += [p for p in perms if p not in RANKS]
    target["permissions"] = ordered

    save_db(db)
    return target


def remove_permission(actor_id: str, target_id: str, permission: str):
    """Remove a permission from target user if actor is allowed.

    Rules enforced are symmetric to add_permission: actor must be at least admin and strictly higher than the permission being removed.
    """
    perm_idx = _rank_index(permission)
    if perm_idx == -1:
        raise HTTPException(status_code=400, detail=f"Unknown permission: {permission}")

    actor = get_user_by_id(actor_id)
    if not actor:
        raise HTTPException(status_code=404, detail="Actor user not found")
    if actor.get("banned"):
        raise HTTPException(status_code=403, detail="Actor is banned")

    actor_highest = highest_rank_index(actor)
    admin_idx = _rank_index("admin")

    if actor_highest < admin_idx:
        raise HTTPException(status_code=403, detail="You don't have permission to modify roles (requires admin or higher).")

    if actor_highest <= perm_idx:
        raise HTTPException(status_code=403, detail="You can't revoke a role equal or higher than your own highest role.")

    db = load_db()
    users = db.setdefault("users", {})
    target = users.get(str(target_id))
    if not target:
        raise HTTPException(status_code=404, detail="Target user not found")

    perms = set(target.get("permissions", []))
    if permission not in perms:
        # No-op
        return target

    perms.remove(permission)
    ordered = [p for p in RANKS if p in perms]
    ordered += [p for p in perms if p not in RANKS]
    target["permissions"] = ordered

    save_db(db)
    return target


def ban_user(actor_id: str, target_id: str, reason: str | None = None):
    """Ban a target user if actor is allowed."""
    actor = get_user_by_id(actor_id)
    if not actor:
        raise HTTPException(status_code=404, detail="Actor user not found")
    if actor.get("banned"):
        raise HTTPException(status_code=403, detail="Actor is banned")

    if str(actor_id) == str(target_id):
        raise HTTPException(status_code=403, detail="You can't ban yourself")

    actor_highest = highest_rank_index(actor)
    admin_idx = _rank_index("admin")
    if actor_highest < admin_idx:
        raise HTTPException(status_code=403, detail="You don't have permission to ban users (requires admin or higher).")

    db = load_db()
    users = db.setdefault("users", {})
    target = users.get(str(target_id))
    if not target:
        raise HTTPException(status_code=404, detail="Target user not found")

    target_highest = highest_rank_index(target)
    if actor_highest <= target_highest:
        raise HTTPException(status_code=403, detail="You can't ban a user with equal or higher rank.")

    clean_reason = (reason or "").strip() or None
    target["banned"] = True
    target["reason"] = clean_reason

    save_db(db)
    return target


def unban_user(actor_id: str, target_id: str):
    """Unban a target user if actor is allowed."""
    actor = get_user_by_id(actor_id)
    if not actor:
        raise HTTPException(status_code=404, detail="Actor user not found")
    if actor.get("banned"):
        raise HTTPException(status_code=403, detail="Actor is banned")

    actor_highest = highest_rank_index(actor)
    admin_idx = _rank_index("admin")
    if actor_highest < admin_idx:
        raise HTTPException(status_code=403, detail="You don't have permission to unban users (requires admin or higher).")

    db = load_db()
    users = db.setdefault("users", {})
    target = users.get(str(target_id))
    if not target:
        raise HTTPException(status_code=404, detail="Target user not found")

    target_highest = highest_rank_index(target)
    if actor_highest <= target_highest:
        raise HTTPException(status_code=403, detail="You can't unban a user with equal or higher rank.")

    target["banned"] = False
    target["reason"] = None

    save_db(db)
    return target


def create_user(actor_id: str, user_id: str, name: str, permissions: list[str] | None = None):
    actor = get_user_by_id(actor_id)
    if not actor:
        raise HTTPException(status_code=404, detail="Actor user not found")
    if actor.get("banned"):
        raise HTTPException(status_code=403, detail="Actor is banned")

    actor_highest = highest_rank_index(actor)
    admin_idx = _rank_index("admin")
    if actor_highest < admin_idx:
        raise HTTPException(status_code=403, detail="You don't have permission to create users (requires admin or higher).")

    clean_id = str(user_id).strip()
    clean_name = (name or "").strip()
    if not clean_id:
        raise HTTPException(status_code=400, detail="User ID is required")
    if not clean_name:
        raise HTTPException(status_code=400, detail="Name is required")

    requested = [p for p in (permissions or []) if p]
    # Keep empty list if nothing is selected.

    for perm in requested:
        if _rank_index(perm) == -1:
            raise HTTPException(status_code=400, detail=f"Unknown permission: {perm}")
        if actor_highest <= _rank_index(perm):
            raise HTTPException(status_code=403, detail="You can't assign a role equal or higher than your own highest role.")

    db = load_db()
    users = db.setdefault("users", {})
    if clean_id in users:
        raise HTTPException(status_code=409, detail="User ID already exists")

    ordered = [p for p in RANKS if p in requested]
    ordered += [p for p in requested if p not in RANKS]

    users[clean_id] = {
        "name": clean_name,
        "permissions": ordered,
        "banned": False,
        "reason": None
    }

    save_db(db)
    return {"id": clean_id, **users[clean_id]}


def delete_user(actor_id: str, target_id: str):
    actor = get_user_by_id(actor_id)
    if not actor:
        raise HTTPException(status_code=404, detail="Actor user not found")
    if actor.get("banned"):
        raise HTTPException(status_code=403, detail="Actor is banned")

    if str(actor_id) == str(target_id):
        raise HTTPException(status_code=403, detail="You can't delete yourself")

    actor_highest = highest_rank_index(actor)
    admin_idx = _rank_index("admin")
    if actor_highest < admin_idx:
        raise HTTPException(status_code=403, detail="You don't have permission to delete users (requires admin or higher).")

    db = load_db()
    users = db.setdefault("users", {})
    target = users.get(str(target_id))
    if not target:
        raise HTTPException(status_code=404, detail="Target user not found")

    target_highest = highest_rank_index(target)
    if actor_highest <= target_highest:
        raise HTTPException(status_code=403, detail="You can't delete a user with equal or higher rank.")

    deleted = {"id": str(target_id), **target}
    del users[str(target_id)]
    save_db(db)
    return deleted


def _hash_password(password: str, salt: str | None = None) -> str:
    import hashlib
    import secrets

    clean = (password or "").strip()
    if not clean:
        raise HTTPException(status_code=400, detail="Password is required")

    if salt is None:
        salt = secrets.token_hex(16)

    digest = hashlib.sha256(f"{salt}:{clean}".encode("utf-8")).hexdigest()
    return f"{salt}${digest}"


def set_user_password(user_id: str, new_password: str):
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.get("banned"):
        raise HTTPException(status_code=403, detail="User is banned")

    clean = (new_password or "").strip()
    if clean.startswith("74"):
        raise HTTPException(status_code=400, detail="Passwords cannot start with 74")
    if len(clean) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters")

    db = load_db()
    users = db.setdefault("users", {})
    target = users.get(str(user_id))
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    target["password"] = _hash_password(clean)
    save_db(db)
    return {"id": str(user_id)}


def set_user_password_admin(actor_id: str, target_id: str, new_password: str):
    actor = get_user_by_id(actor_id)
    if not actor:
        raise HTTPException(status_code=404, detail="Actor user not found")
    if actor.get("banned"):
        raise HTTPException(status_code=403, detail="Actor is banned")

    actor_highest = highest_rank_index(actor)
    admin_idx = _rank_index("admin")
    if actor_highest < admin_idx:
        raise HTTPException(status_code=403, detail="You don't have permission to set passwords (requires admin or higher).")

    target = get_user_by_id(target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target user not found")

    if str(actor_id) != str(target_id):
        target_highest = highest_rank_index(target)
        if actor_highest <= target_highest:
            raise HTTPException(status_code=403, detail="You can't change a user with equal or higher rank.")

    clean = (new_password or "").strip()
    if clean.startswith("74"):
        raise HTTPException(status_code=400, detail="Passwords cannot start with 74")
    if len(clean) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters")

    db = load_db()
    users = db.setdefault("users", {})
    stored = users.get(str(target_id))
    if not stored:
        raise HTTPException(status_code=404, detail="Target user not found")

    stored["password"] = _hash_password(clean)
    save_db(db)
    return {"id": str(target_id)}


def has_password(user: dict | None) -> bool:
    if not user:
        return False
    return bool(user.get("password"))


def verify_user_password(user_id: str, password: str | None) -> bool:
    import hashlib
    import hmac

    user = get_user_by_id(user_id)
    if not user:
        return False

    stored = user.get("password")
    if not stored:
        return False

    if password is None:
        return False

    clean = password.strip()
    if not clean:
        return False

    if clean.startswith("74"):
        return False

    if "$" not in stored:
        return False

    salt, digest = stored.split("$", 1)
    if not salt or not digest:
        return False

    expected = hashlib.sha256(f"{salt}:{clean}".encode("utf-8")).hexdigest()
    return hmac.compare_digest(expected, digest)


def _parse_valid_until(value: str | None) -> bool:
    if not value:
        return True
    try:
        from datetime import datetime, timezone

        clean = value.rstrip("Z")
        dt = datetime.fromisoformat(clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt >= datetime.now(timezone.utc)
    except ValueError:
        return False


def _get_login_code(user: dict | None) -> dict | None:
    if not user:
        return None
    code = user.get("login_code")
    if isinstance(code, dict):
        return code
    return None


def get_login_code_info(user_id: str) -> dict | None:
    user = get_user_by_id(user_id)
    if not user:
        return None

    entry = _get_login_code(user)
    if not entry:
        return None

    return {
        "remaining_usage": entry.get("remaining_usage"),
        "set_password": entry.get("set_password"),
        "valid_until": entry.get("valid_until")
    }


def verify_login_code(user_id: str, code: str | None) -> str | None:
    user = get_user_by_id(user_id)
    if not user:
        return None

    entry = _get_login_code(user)
    if not entry:
        return None

    if not code or not code.strip():
        return None

    clean_code = code.strip()
    if not clean_code.startswith("74"):
        return None

    entry_code = entry.get("code")
    if not entry_code or not str(entry_code).startswith("74"):
        return None

    if entry_code != clean_code:
        return None

    remaining = entry.get("remaining_usage")
    if not isinstance(remaining, int):
        return None
    if remaining == -1:
        pass
    elif remaining <= 0:
        return None

    if not _parse_valid_until(entry.get("valid_until")):
        db = load_db()
        users = db.setdefault("users", {})
        stored = users.get(str(user_id))
        if stored and "login_code" in stored:
            del stored["login_code"]
            save_db(db)
        return None

    db = load_db()
    users = db.setdefault("users", {})
    stored = users.get(str(user_id))
    if not stored:
        return None

    if remaining == -1:
        pass
    else:
        remaining -= 1
        if remaining <= 0:
            if "login_code" in stored:
                del stored["login_code"]
        else:
            stored.setdefault("login_code", {})["remaining_usage"] = remaining

    save_db(db)

    set_password = entry.get("set_password")
    if set_password not in {"nudge", "forced", "disabled"}:
        set_password = "disabled"
    return set_password


def kill_login_code(user_id: str, mode: str):
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    entry = _get_login_code(user)
    if not entry:
        return {"updated": False}

    if mode not in {"now", "2h"}:
        raise HTTPException(status_code=400, detail="Invalid mode")

    db = load_db()
    users = db.setdefault("users", {})
    stored = users.get(str(user_id))
    if not stored:
        raise HTTPException(status_code=404, detail="User not found")

    if mode == "now":
        if "login_code" in stored:
            del stored["login_code"]
    else:
        from datetime import datetime, timedelta, timezone

        kill_at = datetime.now(timezone.utc) + timedelta(hours=2)
        stored.setdefault("login_code", {})["valid_until"] = kill_at.isoformat().replace("+00:00", "Z")

    save_db(db)
    return {"updated": True, "mode": mode}


def set_login_code_admin(actor_id: str, target_id: str, code: str, remaining_usage: int, set_password: str, valid_until: str | None):
    actor = get_user_by_id(actor_id)
    if not actor:
        raise HTTPException(status_code=404, detail="Actor user not found")
    if actor.get("banned"):
        raise HTTPException(status_code=403, detail="Actor is banned")

    actor_highest = highest_rank_index(actor)
    admin_idx = _rank_index("admin")
    if actor_highest < admin_idx:
        raise HTTPException(status_code=403, detail="You don't have permission to manage login codes (requires admin or higher).")

    target = get_user_by_id(target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target user not found")

    if str(actor_id) != str(target_id):
        target_highest = highest_rank_index(target)
        if actor_highest <= target_highest:
            raise HTTPException(status_code=403, detail="You can't change a user with equal or higher rank.")

    clean_code = (code or "").strip()
    if not clean_code:
        raise HTTPException(status_code=400, detail="Code is required")
    if not clean_code.startswith("74"):
        raise HTTPException(status_code=400, detail="Codes must start with 74")

    if not isinstance(remaining_usage, int) or (remaining_usage < 1 and remaining_usage != -1):
        raise HTTPException(status_code=400, detail="Remaining usage must be at least 1 or -1")

    if set_password not in {"nudge", "forced", "disabled"}:
        raise HTTPException(status_code=400, detail="Invalid set_password value")

    if valid_until is not None:
        clean_until = valid_until.strip()
        if clean_until:
            if not _parse_valid_until(clean_until):
                raise HTTPException(status_code=400, detail="Invalid valid_until value")
        else:
            clean_until = None
    else:
        clean_until = None

    db = load_db()
    users = db.setdefault("users", {})
    stored = users.get(str(target_id))
    if not stored:
        raise HTTPException(status_code=404, detail="Target user not found")

    stored["login_code"] = {
        "code": clean_code,
        "remaining_usage": remaining_usage,
        "set_password": set_password,
        "valid_until": clean_until
    }

    save_db(db)
    return stored["login_code"]
