import os

from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, Header
from pydantic import BaseModel, Field
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth, CacheFileHandler

import cors
import users
from jwt import get_current_user, create_access_token, is_token_valid
import board

load_dotenv()
app = FastAPI()

cors.setup(app)

cache_handler = CacheFileHandler(cache_path=".spotify_cache")

LOCKDOWN = False


def get_auth_manager():
    return SpotifyOAuth(
        client_id=os.getenv("SPOTIFY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
        redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI"),
        scope="user-read-playback-state user-modify-playback-state",
        cache_handler=cache_handler,
        show_dialog=True
    )


def get_sp(auth_manager=Depends(get_auth_manager)):
    token_info = auth_manager.validate_token(cache_handler.get_cached_token())

    if not token_info:
        raise HTTPException(status_code=503,
                            detail="Service unavailable. Please tell your administrator to log in (/login).")

    return Spotify(auth=token_info['access_token'])


def ensure_music_control(payload: dict):
    user_id = payload.get("sub")
    if not users.check_user_perm(user_id, "music"):
        raise HTTPException(status_code=403, detail="You don't have the 'music' permission.")
    if LOCKDOWN and not users.check_user_rank_or_higher(user_id, "moderator"):
        raise HTTPException(status_code=403, detail="System is locked. Moderator or higher required.")


class LockdownRequest(BaseModel):
    locked: bool


class SetPasswordRequest(BaseModel):
    password: str
    confirm: str | None = None


class LoginRequest(BaseModel):
    user_id: str
    password: str | None = None
    code: str | None = None


class LoginCodeRequest(BaseModel):
    code: str
    remaining_usage: int
    set_password: str
    valid_until: str | None = None


class KillLoginCodeRequest(BaseModel):
    mode: str


class BoardUpdateRequest(BaseModel):
    widgets: list[dict] | None = None
    order: list[str] | None = None
    pinned: list[str] | None = None


class BoardPollVoteRequest(BaseModel):
    widget_key: str
    option_id: str


class BoardConfettiRequest(BaseModel):
    particle_count: int | None = Field(default=None, alias="particleCount")
    duration_ms: int | None = Field(default=None, alias="durationMs")
    spawn_duration_ms: int | None = Field(default=None, alias="spawnDurationMs")
    spread: float | None = None
    size_scale: float | None = Field(default=None, alias="sizeScale")
    upward_boost: float | None = Field(default=None, alias="upwardBoost")

    class Config:
        allow_population_by_field_name = True
        populate_by_name = True
        extra = "ignore"


@app.post("/token")
def login_to_app(user_id: str | None = None, password: str | None = None, code: str | None = None, req: LoginRequest | None = None):
    if req is not None:
        user_id = req.user_id
        password = req.password
        code = req.code

    if not user_id:
        raise HTTPException(status_code=400, detail="User ID is required")

    if password is not None and password.strip().startswith("74"):
        raise HTTPException(status_code=400, detail="Use /login/code for code logins")

    user = users.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User ID doesn't exist in users.json")

    set_password = "disabled"

    if password and users.verify_user_password(user_id, password):
        pass
    else:
        set_password = users.verify_login_code(user_id, code) or "disabled"
        if set_password == "disabled":
            if users.has_password(user):
                raise HTTPException(status_code=401, detail="Password required or invalid")

    access_token = create_access_token(user_id)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "set_password": set_password
    }


@app.post("/check")
def check_session(x_session_id: str = Header(None)):
    valid = is_token_valid(x_session_id)
    return {"valid": valid}


@app.get("/me")
def get_me(payload: dict = Depends(get_current_user)):
    user_id = payload.get("sub")
    user = users.get_user_by_id(user_id)

    if not user:
        return {"real": False}

    return {
        "real": True,
        "id": user_id,
        "name": user["name"],
        "permissions": user.get("permissions", []),
        "banned": user.get("banned", False),
        "reason": user.get("reason", False)
    }


@app.post("/me/password")
def set_my_password(req: SetPasswordRequest, payload: dict = Depends(get_current_user)):
    if req.confirm is not None and req.password != req.confirm:
        raise HTTPException(status_code=400, detail="Passwords do not match")
    user_id = payload.get("sub")
    users.set_user_password(user_id, req.password)
    return {"ok": True}


@app.get("/me/login-code")
def get_my_login_code(payload: dict = Depends(get_current_user)):
    user_id = payload.get("sub")
    info = users.get_login_code_info(user_id)
    if not info:
        return {"has_code": False}
    return {"has_code": True, "login_code": info}


@app.get("/admin/spotify/login")
def login(auth_manager=Depends(get_auth_manager), payload: dict = Depends(get_current_user)):
    if not users.check_user_perm(payload.get("sub"), "admin"):
        raise HTTPException(status_code=403, detail="You don't have the 'admin' permission.")
    auth_url = auth_manager.get_authorize_url()
    return {"login_uri": auth_url}


@app.get("/callback")
def callback(code: str, auth_manager=Depends(get_auth_manager), payload: dict = Depends(get_current_user)):
    if not users.check_user_perm(payload.get("sub"), "admin"):
        raise HTTPException(status_code=403, detail="You don't have the 'admin' permission.")
    auth_manager.get_access_token(code)
    return {"message": "Login successful."}


@app.get("/admin/spotify/logout")
def logout(payload: dict = Depends(get_current_user)):
    if not users.check_user_perm(payload.get("sub"), "admin"):
        raise HTTPException(status_code=403, detail="You don't have the 'admin' permission.")
    cache_path = ".spotify_cache"
    if os.path.exists(cache_path):
        os.remove(cache_path)
        return {"message": "Logged out successfully."}
    return {"message": "Already logged out."}


@app.get("/status")
def get_status(sp: Spotify = Depends(get_sp)):  # no auth
    return sp.current_user_playing_track()


@app.get("/search")
def search(q: str, limit: int = 5, sp: Spotify = Depends(get_sp), payload: dict = Depends(get_current_user)):
    if not users.check_user_perm(payload.get("sub"), "music"):
        raise HTTPException(status_code=403, detail="You don't have the 'music' permission.")
    return sp.search(q=q, limit=limit, type="track")


@app.post("/add")
def add_to_queue(uri: str, sp: Spotify = Depends(get_sp), payload: dict = Depends(get_current_user)):
    ensure_music_control(payload)
    sp.add_to_queue(uri=uri)
    return {"message": f"nailed it"}


@app.post("/play")
def play_now(uri: str, sp: Spotify = Depends(get_sp), payload: dict = Depends(get_current_user)):
    ensure_music_control(payload)
    sp.start_playback(uris=[uri])
    return {"message": f"nailed it"}


@app.get("/list-queue")
def list_queue(sp: Spotify = Depends(get_sp)):  # no auth
    return sp.queue()


@app.post("/pause")
def pause(sp: Spotify = Depends(get_sp), payload: dict = Depends(get_current_user)):
    ensure_music_control(payload)
    sp.pause_playback()
    return {"message": "nailed it"}


@app.post("/resume")
def resume(sp: Spotify = Depends(get_sp), payload: dict = Depends(get_current_user)):
    ensure_music_control(payload)
    sp.start_playback()
    return {"message": "nailed it"}


@app.post("/next")
def skip_track(sp: Spotify = Depends(get_sp), payload: dict = Depends(get_current_user)):
    ensure_music_control(payload)
    sp.next_track()
    return {"message": "nailed it"}


@app.post("/previous")
def previous_track(sp: Spotify = Depends(get_sp), payload: dict = Depends(get_current_user)):
    ensure_music_control(payload)
    sp.previous_track()
    return {"message": "nailed it"}


@app.post("/admin/users/{target_id}/permissions")
def grant_permission(target_id: str, permission: str, payload: dict = Depends(get_current_user)):
    """Grant a permission to a target user. Caller must be admin or higher and must be higher ranked than the permission they grant."""
    actor_id = payload.get("sub")
    # users.add_permission will perform all checks and raise HTTPException on failure
    updated = users.add_permission(actor_id, target_id, permission)
    return {"message": "permission added", "user": updated}


@app.delete("/admin/users/{target_id}/permissions")
def revoke_permission(target_id: str, permission: str, payload: dict = Depends(get_current_user)):
    """Revoke a permission from a target user. Caller must be admin or higher and must be higher ranked than the permission they revoke."""
    actor_id = payload.get("sub")
    updated = users.remove_permission(actor_id, target_id, permission)
    return {"message": "permission removed", "user": updated}


@app.post("/admin/users/{target_id}/ban")
def ban_user(target_id: str, reason: str | None = None, payload: dict = Depends(get_current_user)):
    """Ban a user. Caller must be admin or higher and higher ranked than target."""
    actor_id = payload.get("sub")
    updated = users.ban_user(actor_id, target_id, reason)
    return {"message": "user banned", "user": updated}


@app.delete("/admin/users/{target_id}/ban")
def unban_user(target_id: str, payload: dict = Depends(get_current_user)):
    """Unban a user. Caller must be admin or higher and higher ranked than target."""
    actor_id = payload.get("sub")
    updated = users.unban_user(actor_id, target_id)
    return {"message": "user unbanned", "user": updated}


class CreateUserRequest(BaseModel):
    id: str
    name: str
    permissions: list[str] | None = None


@app.get("/admin/users")
def list_users_admin(payload: dict = Depends(get_current_user)):
    if not users.check_user_perm(payload.get("sub"), "admin"):
        raise HTTPException(status_code=403, detail="You don't have the 'admin' permission.")

    return {"users": users.list_users()}


@app.post("/admin/users")
def create_user_admin(req: CreateUserRequest, payload: dict = Depends(get_current_user)):
    actor_id = payload.get("sub")
    created = users.create_user(actor_id, req.id, req.name, req.permissions)
    return {"message": "user created", "user": created}


@app.post("/admin/users/{target_id}/password")
def set_user_password_admin(target_id: str, req: SetPasswordRequest, payload: dict = Depends(get_current_user)):
    if req.confirm is not None and req.password != req.confirm:
        raise HTTPException(status_code=400, detail="Passwords do not match")
    actor_id = payload.get("sub")
    users.set_user_password_admin(actor_id, target_id, req.password)
    return {"ok": True}


@app.delete("/admin/users/{target_id}")
def delete_user_admin(target_id: str, payload: dict = Depends(get_current_user)):
    actor_id = payload.get("sub")
    deleted = users.delete_user(actor_id, target_id)
    return {"message": "user deleted", "user": deleted}


@app.get("/admin/users/{target_id}")
def get_user_admin(target_id: str, payload: dict = Depends(get_current_user)):
    if not users.check_user_perm(payload.get("sub"), "admin"):
        raise HTTPException(status_code=403, detail="You don't have the 'admin' permission.")

    user = users.get_user_by_id(target_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "user": {
            "id": target_id,
            "name": user.get("name"),
            "permissions": user.get("permissions", []),
            "banned": user.get("banned", False),
            "reason": user.get("reason", False),
            "has_password": users.has_password(user)
        }
    }


@app.post("/admin/users/{target_id}/login-code")
def set_login_code_admin(target_id: str, req: LoginCodeRequest, payload: dict = Depends(get_current_user)):
    actor_id = payload.get("sub")
    login_code = users.set_login_code_admin(
        actor_id,
        target_id,
        req.code,
        req.remaining_usage,
        req.set_password,
        req.valid_until
    )
    return {"login_code": login_code}


@app.post("/me/login-code/kill")
def kill_my_login_code(req: KillLoginCodeRequest, payload: dict = Depends(get_current_user)):
    user_id = payload.get("sub")
    result = users.kill_login_code(user_id, req.mode)
    return result


@app.get("/lockdown")
def get_lockdown():  # no auth
    return {"locked": LOCKDOWN}


@app.post("/lockdown")
def set_lockdown(req: LockdownRequest | None = None, locked: bool | None = None, payload: dict = Depends(get_current_user)):
    if not users.check_user_rank_or_higher(payload.get("sub"), "moderator"):
        raise HTTPException(status_code=403, detail="You don't have the 'moderator' permission.")
    value = req.locked if req is not None else locked
    if value is None:
        raise HTTPException(status_code=400, detail="Missing 'locked' value.")
    global LOCKDOWN
    LOCKDOWN = bool(value)
    return {"locked": LOCKDOWN}


@app.get("/board")
def get_board():
    return board.load_board()


@app.put("/board")
def update_board(req: BoardUpdateRequest, payload: dict = Depends(get_current_user)):
    user_id = payload.get("sub")
    if not users.check_user_rank_or_higher(user_id, "music"):
        raise HTTPException(status_code=403, detail="You don't have the 'music' permission.")
    if req.pinned is not None and not users.check_user_perm(user_id, "admin"):
        raise HTTPException(status_code=403, detail="You don't have the 'admin' permission.")
    return board.update_board(
        widgets=req.widgets,
        order_ids=req.order,
        pinned_ids=req.pinned,
        updated_by=user_id
    )


@app.post("/board/poll/vote")
def vote_on_poll(req: BoardPollVoteRequest):
    updated = board.vote_poll(req.widget_key, req.option_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Poll option not found")
    return {"option": updated}


@app.post("/board/confetti")
def trigger_board_confetti(req: BoardConfettiRequest, payload: dict = Depends(get_current_user)):
    user_id = payload.get("sub")
    if not users.check_user_rank_or_higher(user_id, "music"):
        raise HTTPException(status_code=403, detail="You don't have the 'music' permission.")
    config = req.dict(by_alias=True, exclude_none=True)
    trigger = board.set_confetti_trigger(config=config, updated_by=user_id)
    return {"ok": True, "trigger": trigger}
