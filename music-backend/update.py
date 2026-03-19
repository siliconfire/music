import os
import subprocess

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_URL = "https://github.com/siliconfire/music.git"
REMOTE_NAME = "origin"
BRANCH = "master"


def _git(args: list[str], check: bool = True, capture_output: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_DIR,
        check=check,
        text=True,
        capture_output=capture_output,
    )


def _is_git_repo() -> bool:
    try:
        _git(["rev-parse", "--is-inside-work-tree"], capture_output=True)
        return True
    except Exception:
        return False


def _ensure_remote() -> bool:
    try:
        result = _git(["remote", "get-url", REMOTE_NAME], check=False, capture_output=True)
        current_url = (result.stdout or "").strip()
        if result.returncode != 0:
            _git(["remote", "add", REMOTE_NAME, REPO_URL])
        elif current_url != REPO_URL:
            _git(["remote", "set-url", REMOTE_NAME, REPO_URL])
        return True
    except Exception as exc:
        print(f"[update] remote setup failed: {exc}")
        return False


def _working_tree_clean() -> bool:
    try:
        # Ignore untracked files so local logs/cache files do not block updates.
        result = _git(["status", "--porcelain", "--untracked-files=no"], capture_output=True)
        return (result.stdout or "").strip() == ""
    except Exception:
        return False


def _sync_state() -> str:
    """Return one of: up_to_date, behind, ahead, diverged, unknown."""
    try:
        _git(["fetch", REMOTE_NAME, BRANCH])
        result = _git(["rev-list", "--left-right", "--count", f"HEAD...{REMOTE_NAME}/{BRANCH}"], capture_output=True)
        parts = (result.stdout or "").strip().split()
        if len(parts) != 2:
            return "unknown"
        ahead = int(parts[0])
        behind = int(parts[1])
        if ahead == 0 and behind == 0:
            return "up_to_date"
        if ahead == 0 and behind > 0:
            return "behind"
        if ahead > 0 and behind == 0:
            return "ahead"
        return "diverged"
    except Exception:
        return "unknown"


def _message_for_state(state: str) -> str:
    if state == "up_to_date":
        return "already up to date"
    if state == "behind":
        return "update available"
    if state == "ahead":
        return "local branch is ahead of remote"
    if state == "diverged":
        return "local and remote branches diverged"
    return "unable to determine sync state"


def get_status() -> dict:
    if not _is_git_repo():
        return {
            "ok": False,
            "state": "unknown",
            "clean": False,
            "message": "not a git repository",
            "remote": REMOTE_NAME,
            "branch": BRANCH,
        }
    if not _ensure_remote():
        return {
            "ok": False,
            "state": "unknown",
            "clean": _working_tree_clean(),
            "message": "remote setup failed",
            "remote": REMOTE_NAME,
            "branch": BRANCH,
        }

    state = _sync_state()
    return {
        "ok": state != "unknown",
        "state": state,
        "clean": _working_tree_clean(),
        "message": _message_for_state(state),
        "remote": REMOTE_NAME,
        "branch": BRANCH,
    }


def check_updates() -> bool:
    status = get_status()
    if not status.get("ok"):
        print(f"[update] check failed: {status.get('message')}")
        return False
    if status["state"] == "behind":
        print("[update] update available")
        return True
    print(f"[update] skipped: {status.get('message')}")
    return False


def main() -> bool:
    status = get_status()
    if not status.get("ok"):
        print(f"[update] failed: {status.get('message')}")
        return False
    if not status.get("clean"):
        print("[update] skipped: working tree has local changes")
        return False
    if status["state"] != "behind":
        print(f"[update] skipped: {status.get('message')}")
        return False

    try:
        _git(["pull", "--ff-only", REMOTE_NAME, BRANCH])
        print("[update] pull completed")
        return True
    except Exception as exc:
        print(f"[update] pull failed: {exc}")
        return False


def force_sync() -> bool:
    """One-way sync from remote by discarding local tracked changes/commits."""
    status = get_status()
    if not status.get("ok"):
        print(f"[update] force sync failed: {status.get('message')}")
        return False
    try:
        _git(["fetch", REMOTE_NAME, BRANCH])
        _git(["reset", "--hard", f"{REMOTE_NAME}/{BRANCH}"])
        print("[update] force sync completed")
        return True
    except Exception as exc:
        print(f"[update] force sync failed: {exc}")
        return False


if __name__ == "__main__":
    if check_updates():
        main()
