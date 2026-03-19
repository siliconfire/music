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
        result = _git(["status", "--porcelain"], capture_output=True)
        return (result.stdout or "").strip() == ""
    except Exception:
        return False


def check_updates() -> bool:
    if not _is_git_repo():
        print("[update] skipped: not a git repository")
        return False
    if not _ensure_remote():
        return False

    try:
        _git(["fetch", REMOTE_NAME, BRANCH])
        local_sha = (_git(["rev-parse", "HEAD"], capture_output=True).stdout or "").strip()
        remote_sha = (_git(["rev-parse", f"{REMOTE_NAME}/{BRANCH}"], capture_output=True).stdout or "").strip()
        has_update = bool(local_sha and remote_sha and local_sha != remote_sha)
        print("[update] update available" if has_update else "[update] already up to date")
        return has_update
    except Exception as exc:
        print(f"[update] check failed: {exc}")
        return False


def main() -> bool:
    if not _is_git_repo():
        print("[update] failed: not a git repository")
        return False
    if not _ensure_remote():
        return False
    if not _working_tree_clean():
        print("[update] skipped: working tree has local changes")
        return False

    try:
        _git(["pull", "--ff-only", REMOTE_NAME, BRANCH])
        print("[update] pull completed")
        return True
    except Exception as exc:
        print(f"[update] pull failed: {exc}")
        return False


if __name__ == "__main__":
    if check_updates():
        main()
