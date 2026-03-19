import os
import base64
import json
import time
import uuid
import threading
import requests

from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, Header, Security
from pydantic import BaseModel, Field
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth, CacheFileHandler
from webauthn import (
    generate_registration_options,
    generate_authentication_options,
    verify_registration_response,
    verify_authentication_response,
    options_to_json
)
from webauthn.helpers.structs import (
    RegistrationCredential,
    AuthenticationCredential,
    PublicKeyCredentialDescriptor,
    PublicKeyCredentialType,
    UserVerificationRequirement,
    ResidentKeyRequirement,
    AuthenticatorSelectionCriteria,
    AttestationConveyancePreference
)

import cors
import users
import update as updater
from jwt import get_current_user, create_access_token, create_permanent_token, is_token_valid, api_key_header
import board
from content_checker import content_checker, reload_blacklists, find_blacklist_match
import logging

# Logger for blocked content checks
content_logger = logging.getLogger("content_checks")
if not content_logger.handlers:
    handler = logging.FileHandler("content_checks.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s\t%(levelname)s\t%(message)s"))
    content_logger.addHandler(handler)
content_logger.setLevel(logging.INFO)
content_logger.propagate = False

load_dotenv()
app = FastAPI()

UPDATE_INTERVAL_SECONDS = 60 * 60
_update_lock = threading.Lock()
_update_stop_event = threading.Event()
_update_thread: threading.Thread | None = None
update_logger = logging.getLogger("auto_update")


def run_update_cycle():
    # Guard against overlapping runs when an update takes longer than the interval.
    if not _update_lock.acquire(blocking=False):
        update_logger.info("Update cycle skipped: previous cycle is still running.")
        return

    original_cwd = os.getcwd()
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        os.chdir(backend_dir)
        if updater.check_updates():
            update_logger.info("Update found. Running updater.")
            updater.main()
        else:
            update_logger.info("No update found.")
    except Exception:
        update_logger.exception("Auto-update cycle failed.")
    finally:
        os.chdir(original_cwd)
        _update_lock.release()


def update_scheduler_loop():
    run_update_cycle()
    while not _update_stop_event.wait(UPDATE_INTERVAL_SECONDS):
        run_update_cycle()


@app.on_event("startup")
def start_update_scheduler():
    global _update_thread
    if _update_thread and _update_thread.is_alive():
        return
    _update_stop_event.clear()
    _update_thread = threading.Thread(target=update_scheduler_loop, name="auto-updater", daemon=True)
    _update_thread.start()


@app.on_event("shutdown")
def stop_update_scheduler():
    _update_stop_event.set()
    if _update_thread and _update_thread.is_alive():
        _update_thread.join(timeout=2)

cors.setup(app)

cache_handler = CacheFileHandler(cache_path=".spotify_cache")

LOCKDOWN = False
BOARD_LOCKDOWN = False

PASSKEY_RP_ID = os.getenv("PASSKEY_RP_ID", "localhost")
PASSKEY_RP_ORIGIN = os.getenv("PASSKEY_RP_ORIGIN", "http://localhost:4321")
PASSKEY_RP_NAME = os.getenv("PASSKEY_RP_NAME", "Bartın Lisesi Müzik Sistemi")
PASSKEY_CHALLENGE_TTL_SEC = 300
PASSKEY_REGISTER_CHALLENGES: dict[str, dict] = {}
PASSKEY_LOGIN_CHALLENGES: dict[str, dict] = {}
BOARD_LOGIN_APPROVALS: dict[str, dict] = {}
BOARD_LOGIN_TTL_SEC = 300
SPOTIFY_OAUTH_STATES: dict[str, dict] = {}
SPOTIFY_OAUTH_STATE_TTL_SEC = 600
SPOTIFY_REQUEST_TIMEOUT_SEC = float(os.getenv("SPOTIFY_REQUEST_TIMEOUT_SEC", "10"))


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
                            detail="Hayır. Maalesef hayır. Lütfen yöneticinizden giriş yapmasını isteyin.")

    return Spotify(auth=token_info["access_token"], requests_timeout=SPOTIFY_REQUEST_TIMEOUT_SEC)


def ensure_music_control(payload: dict):
    user_id = payload.get("sub")
    if not users.check_user_perm(user_id, "music"):
        raise HTTPException(status_code=403, detail="'music' yetkisine sahip değilsiniz.")
    if LOCKDOWN and not users.check_user_rank_or_higher(user_id, "moderator"):
        raise HTTPException(status_code=403, detail="Sistem kilitli, kilitli iken değişiklik yapmak için moderatör veya üstü olmanız gerekir. Daha fazla bilgi için yardım alın.")


def ensure_board_edit(payload: dict):
    user_id = payload.get("sub")
    if BOARD_LOCKDOWN and not users.check_user_rank_or_higher(user_id, "moderator"):
        raise HTTPException(status_code=403, detail="Düzenleme kilitli, kilitli iken değişiklik yapmak için moderatör veya üstü olmanız gerekir. Daha fazla bilgi için yardım alın.")


class LockdownRequest(BaseModel):
    locked: bool


class BoardLockdownRequest(BaseModel):
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


class AdminUpdateRunRequest(BaseModel):
    force: bool = False


class BoardUpdateRequest(BaseModel):
    widgets: list[dict] | None = None
    order: list[str] | None = None
    pinned: list[str] | None = None
    theme_key: str | None = None
    background_image_key: str | None = None
    background_image_url: str | None = None
    backdrop_blur_px: int | None = None
    card_blur_px: int | None = None


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


class BoardRedirectRequest(BaseModel):
    path: str | None = None

    class Config:
        extra = "ignore"


class BoardPasskeysRequest(BaseModel):
    passkeys: list[str] | None = None


class PasskeyRegistrationVerifyRequest(BaseModel):
    challenge_id: str
    credential: dict


class PasskeyAuthenticationOptionsRequest(BaseModel):
    user_id: str | None = None


class PasskeyAuthenticationVerifyRequest(BaseModel):
    challenge_id: str
    credential: dict


@app.post("/token")
def login_to_app(user_id: str | None = None, password: str | None = None, code: str | None = None, req: LoginRequest | None = None):
    if req is not None:
        user_id = req.user_id
        password = req.password
        code = req.code

    if not user_id:
        raise HTTPException(status_code=400, detail="ID girmezsen ben kim olduğunu nereden bilebilirim?")

    if password is not None and password.strip().startswith("74"):
        raise HTTPException(status_code=400, detail="stupid.")

    user = users.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="böyle bir kullanıcı yok...? doğru ID girdiğinden emin misin?")

    set_password = "disabled"

    password_ok = bool(password) and users.verify_user_password(user_id, password)

    if not password_ok:
        set_password = users.verify_login_code(user_id, code) or "disabled"
        if set_password == "disabled":
            raise HTTPException(status_code=401, detail="geçersiz, doğru girdiğinizden emin olun")

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


@app.post("/boardlogin/approve")
def board_login_approve(board_id: str = "100000", device_id: str | None = None, payload: dict = Depends(get_current_user)):
    actor_id = payload.get("sub")
    if not users.check_user_rank_or_higher(actor_id, "admin"):
        raise HTTPException(status_code=403, detail="Admin veya üstü yetki gerekli.")
    board_user = users.get_user_by_id(board_id)
    if not board_user:
        raise HTTPException(status_code=404, detail="Board user not found ...?")
    if board_user.get("banned"):
        raise HTTPException(status_code=403, detail="Board user is banned ...?")
    if "board" not in board_user.get("permissions", []):
        raise HTTPException(status_code=400, detail="Board user missing 'board' permission ...?")
    if not device_id:
        raise HTTPException(status_code=400, detail="Device ID gerekli.")
    token = create_permanent_token(board_id)
    BOARD_LOGIN_APPROVALS[device_id] = {
        "created_at": time.time(),
        "token": token,
        "board_id": board_id,
        "approved_by": actor_id
    }
    return {"ok": True, "device_id": device_id}


@app.get("/boardlogin/pending")
def board_login_pending(device_id: str | None = None):
    if not device_id:
        raise HTTPException(status_code=400, detail="Device ID gerekli.")
    payload = _consume_board_login(device_id)
    if not payload:
        return {"ready": False}
    return {"ready": True, "access_token": payload.get("token"), "board_id": payload.get("board_id")}


def _base64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _base64url_decode(value: str) -> bytes:
    padded = value + "=" * ((4 - len(value) % 4) % 4)
    return base64.urlsafe_b64decode(padded)


def _store_challenge(store: dict, payload: dict) -> str:
    challenge_id = uuid.uuid4().hex
    payload["created_at"] = time.time()
    store[challenge_id] = payload
    return challenge_id


def _load_challenge(store: dict, challenge_id: str) -> dict | None:
    payload = store.get(challenge_id)
    if not payload:
        return None
    created_at = payload.get("created_at", 0)
    if time.time() - float(created_at) > PASSKEY_CHALLENGE_TTL_SEC:
        store.pop(challenge_id, None)
        return None
    return payload


def _cleanup_challenges(store: dict):
    now = time.time()
    for key, payload in list(store.items()):
        created_at = payload.get("created_at", 0)
        if now - float(created_at) > PASSKEY_CHALLENGE_TTL_SEC:
            store.pop(key, None)


def _cleanup_board_login():
    now = time.time()
    for key, payload in list(BOARD_LOGIN_APPROVALS.items()):
        created_at = payload.get("created_at", 0)
        if now - float(created_at) > BOARD_LOGIN_TTL_SEC:
            BOARD_LOGIN_APPROVALS.pop(key, None)


def _cleanup_spotify_states():
    now = time.time()
    for key, payload in list(SPOTIFY_OAUTH_STATES.items()):
        created_at = payload.get("created_at", 0)
        if now - float(created_at) > SPOTIFY_OAUTH_STATE_TTL_SEC:
            SPOTIFY_OAUTH_STATES.pop(key, None)


def _consume_board_login(device_id: str):
    _cleanup_board_login()
    payload = BOARD_LOGIN_APPROVALS.pop(device_id, None)
    if not payload:
        return None
    return payload


def _parse_registration_credential(payload: dict) -> RegistrationCredential:
    return RegistrationCredential.parse_raw(json.dumps(payload))


def _parse_authentication_credential(payload: dict) -> AuthenticationCredential:
    return AuthenticationCredential.parse_raw(json.dumps(payload))


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
        raise HTTPException(status_code=400, detail="şifreler uyuşsa ne güzel olurdu")
    user_id = payload.get("sub")
    users.set_user_password(user_id, req.password)
    return {"ok": True}


@app.get("/me/login-code")
def get_my_login_code(payload: dict = Depends(get_current_user)):
    user_id = payload.get("sub")
    login_code = users.get_login_code_info(user_id)
    return {
        "has_code": bool(login_code),
        "login_code": login_code
    }


@app.post("/account/passkeys/options")
def get_account_passkey_options(payload: dict = Depends(get_current_user)):
    user_id = payload.get("sub")
    user = users.get_user_by_id(user_id)
    if not user or user.get("banned"):
        raise HTTPException(status_code=403, detail="User not allowed")

    exclude_credentials = []
    for entry in users.get_user_passkeys(user):
        try:
            exclude_credentials.append(
                PublicKeyCredentialDescriptor(
                    type=PublicKeyCredentialType.PUBLIC_KEY,
                    id=_base64url_decode(entry["id"])
                )
            )
        except Exception:
            continue

    options = generate_registration_options(
        rp_id=PASSKEY_RP_ID,
        rp_name=PASSKEY_RP_NAME,
        user_id=str(user_id),
        user_name=user.get("name") or str(user_id),
        user_display_name=user.get("name") or str(user_id),
        exclude_credentials=exclude_credentials,
        attestation=AttestationConveyancePreference.NONE,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.DISCOURAGED
        )
    )

    _cleanup_challenges(PASSKEY_REGISTER_CHALLENGES)
    challenge_id = _store_challenge(PASSKEY_REGISTER_CHALLENGES, {
        "user_id": user_id,
        "challenge": options.challenge
    })

    return {
        "challenge_id": challenge_id,
        "options": json.loads(options_to_json(options))
    }


@app.post("/account/passkeys/verify")
def verify_account_passkey(req: PasskeyRegistrationVerifyRequest, payload: dict = Depends(get_current_user)):
    user_id = payload.get("sub")
    user = users.get_user_by_id(user_id)
    if not user or user.get("banned"):
        raise HTTPException(status_code=403, detail="Hayır.")

    stored = _load_challenge(PASSKEY_REGISTER_CHALLENGES, req.challenge_id)
    if not stored or stored.get("user_id") != user_id:
        raise HTTPException(status_code=400, detail="imkansız (süresi geçmiş olabilir mi?)")

    credential = _parse_registration_credential(req.credential)
    info = verify_registration_response(
        credential=credential,
        expected_challenge=stored["challenge"],
        expected_rp_id=PASSKEY_RP_ID,
        expected_origin=PASSKEY_RP_ORIGIN,
        require_user_verification=False
    )

    credential_id = _base64url_encode(info.credential_id)
    public_key = _base64url_encode(info.credential_public_key)
    users.add_user_passkey(user_id, credential_id, public_key, info.sign_count)
    PASSKEY_REGISTER_CHALLENGES.pop(req.challenge_id, None)
    return {"ok": True, "credential_id": credential_id}


@app.post("/login/passkeys/options")
def get_login_passkey_options(req: PasskeyAuthenticationOptionsRequest | None = None):
    user_id = req.user_id if req else None
    allow_credentials = []
    if user_id:
        user = users.get_user_by_id(user_id)
        if not user or user.get("banned"):
            raise HTTPException(status_code=403, detail="hayır.")
        for entry in users.get_user_passkeys(user):
            try:
                allow_credentials.append(
                    PublicKeyCredentialDescriptor(
                        type=PublicKeyCredentialType.PUBLIC_KEY,
                        id=_base64url_decode(entry["id"])
                    )
                )
            except Exception:
                continue

    options = generate_authentication_options(
        rp_id=PASSKEY_RP_ID,
        user_verification=UserVerificationRequirement.DISCOURAGED,
        allow_credentials=allow_credentials or None
    )

    _cleanup_challenges(PASSKEY_LOGIN_CHALLENGES)
    challenge_id = _store_challenge(PASSKEY_LOGIN_CHALLENGES, {
        "challenge": options.challenge,
        "user_id": user_id
    })

    return {
        "challenge_id": challenge_id,
        "options": json.loads(options_to_json(options))
    }


@app.post("/login/passkeys/verify")
def verify_login_passkey(req: PasskeyAuthenticationVerifyRequest):
    stored = _load_challenge(PASSKEY_LOGIN_CHALLENGES, req.challenge_id)
    if not stored:
        raise HTTPException(status_code=400, detail="imkansız (süresi geçmiş olabilir mi?)")

    credential = _parse_authentication_credential(req.credential)
    credential_id = _base64url_encode(credential.raw_id)
    user_id, user, entry = users.find_user_by_passkey_id(credential_id)
    if not user or not entry:
        raise HTTPException(status_code=401, detail="bu hata mesajını görüyorsan artık muhtemelen türkçe yazmamı haketmiyorsun. Unknown credential.")
    if user.get("banned"):
        raise HTTPException(status_code=403, detail="Kullanıcının hesabı kapatılmış.")

    public_key_bytes = _base64url_decode(entry["public_key"])
    info = verify_authentication_response(
        credential=credential,
        expected_challenge=stored["challenge"],
        expected_rp_id=PASSKEY_RP_ID,
        expected_origin=PASSKEY_RP_ORIGIN,
        credential_public_key=public_key_bytes,
        credential_current_sign_count=entry.get("sign_count", 0),
        require_user_verification=False
    )

    users.update_passkey_sign_count(user_id, credential_id, info.new_sign_count)
    PASSKEY_LOGIN_CHALLENGES.pop(req.challenge_id, None)

    access_token = create_access_token(user_id)
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }


@app.get("/admin/spotify/login")
def login(auth_manager=Depends(get_auth_manager), payload: dict = Depends(get_current_user)):
    if not users.check_user_perm(payload.get("sub"), "admin"):
        raise HTTPException(status_code=403, detail="'admin' yetkisine sahip değilsiniz.")
    actor_id = payload.get("sub")
    _cleanup_spotify_states()
    state = uuid.uuid4().hex
    SPOTIFY_OAUTH_STATES[state] = {
        "user_id": actor_id,
        "created_at": time.time()
    }
    auth_url = auth_manager.get_authorize_url(state=state)
    return {"login_uri": auth_url}


@app.get("/callback")
def callback(code: str, state: str | None = None, auth_manager=Depends(get_auth_manager)):
    if not state:
        raise HTTPException(status_code=400, detail="Missing OAuth state")

    _cleanup_spotify_states()
    payload = SPOTIFY_OAUTH_STATES.pop(state, None)
    if not payload:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")

    actor_id = payload.get("user_id")
    if not users.check_user_perm(actor_id, "admin"):
        raise HTTPException(status_code=403, detail="'admin' yetkisine sahip değilsiniz.")

    auth_manager.get_access_token(code)
    return {"message": "Login successful."}


@app.get("/admin/spotify/logout")
def logout(payload: dict = Depends(get_current_user)):
    if not users.check_user_perm(payload.get("sub"), "admin"):
        raise HTTPException(status_code=403, detail="'admin' yetkisine sahip değilsiniz.")
    cache_path = ".spotify_cache"
    if os.path.exists(cache_path):
        os.remove(cache_path)
        return {"message": "Logged out successfully."}
    return {"message": "Already logged out."}


@app.get("/admin/spotify/devices")
def list_devices(sp: Spotify = Depends(get_sp), payload: dict = Depends(get_current_user)):
    if not users.check_user_perm(payload.get("sub"), "music"):
        raise HTTPException(status_code=403, detail="'music' yetkisine sahip değilsiniz.")
    return sp.devices()


@app.post("/admin/spotify/device")
def set_device(device_id: str, sp: Spotify = Depends(get_sp), payload: dict = Depends(get_current_user)):
    ensure_music_control(payload)
    sp.transfer_playback(device_id=device_id, force_play=False)
    return {"message": "playback transferred"}


@app.get("/status")
def get_status(sp: Spotify = Depends(get_sp)):  # no auth
    return sp.current_user_playing_track()


@app.get("/search")
def search(q: str, limit: int = 5, sp: Spotify = Depends(get_sp), payload: dict = Depends(get_current_user)):
    if not users.check_user_perm(payload.get("sub"), "music"):
        raise HTTPException(status_code=403, detail="'music' yetkisine sahip değilsiniz.")
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
    try:
        return sp.queue()
    except requests.exceptions.ReadTimeout:
        raise HTTPException(status_code=504, detail="Spotify'a ulaşmaya çalışırken bir yanıt alamadık (timeout).")
    except requests.exceptions.RequestException:
        raise HTTPException(status_code=502, detail="Spotify'a ulaşmaya çalışırken bir hata oluştu.")


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
        raise HTTPException(status_code=403, detail="'admin' yetkisine sahip değilsiniz.")

    return {"users": users.list_users()}


@app.post("/admin/users")
def create_user_admin(req: CreateUserRequest, payload: dict = Depends(get_current_user)):
    actor_id = payload.get("sub")
    created = users.create_user(actor_id, req.id, req.name, req.permissions)
    return {"message": "user created", "user": created}


@app.post("/admin/users/{target_id}/password")
def set_user_password_admin(target_id: str, req: SetPasswordRequest, payload: dict = Depends(get_current_user)):
    if req.confirm is not None and req.password != req.confirm:
        raise HTTPException(status_code=400, detail="şifreler uyuşsa ne güzel olurdu")
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
        raise HTTPException(status_code=403, detail="'admin' yetkisine sahip değilsiniz.")

    user = users.get_user_by_id(target_id)
    if not user:
        raise HTTPException(status_code=404, detail="yok. öyle biri yok.")

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


@app.get("/admin/update/status")
def admin_update_status(payload: dict = Depends(get_current_user)):
    if not users.check_user_perm(payload.get("sub"), "admin"):
        raise HTTPException(status_code=403, detail="'admin' yetkisine sahip değilsiniz.")
    return updater.get_status()


@app.post("/admin/update/run")
def admin_update_run(req: AdminUpdateRunRequest | None = None, force: bool | None = None, payload: dict = Depends(get_current_user)):
    if not users.check_user_perm(payload.get("sub"), "admin"):
        raise HTTPException(status_code=403, detail="'admin' yetkisine sahip değilsiniz.")

    force_mode = req.force if req is not None else bool(force)

    if not _update_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Güncelleme zaten çalışıyor.")

    try:
        if force_mode:
            ok = updater.force_sync()
            return {
                "ok": ok,
                "mode": "force",
                "status": updater.get_status()
            }

        has_update = updater.check_updates()
        if not has_update:
            return {
                "ok": True,
                "changed": False,
                "mode": "normal",
                "status": updater.get_status(),
                "message": "Yeni bir güncelleme bulunamadı."
            }

        ok = updater.main()
        return {
            "ok": ok,
            "changed": ok,
            "mode": "normal",
            "status": updater.get_status(),
            "message": "Güncelleme uygulandı." if ok else "Güncelleme uygulanamadı."
        }
    finally:
        _update_lock.release()


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
        raise HTTPException(status_code=403, detail="'moderator' yetkisine sahip değilsiniz.")
    value = req.locked if req is not None else locked
    if value is None:
        raise HTTPException(status_code=400, detail="Missing 'locked' value.")
    global LOCKDOWN
    LOCKDOWN = bool(value)
    return {"locked": LOCKDOWN}


@app.get("/board/lockdown")
def get_board_lockdown():  # no auth
    return {"locked": BOARD_LOCKDOWN}


@app.post("/board/lockdown")
def set_board_lockdown(req: BoardLockdownRequest | None = None, locked: bool | None = None, payload: dict = Depends(get_current_user)):
    if not users.check_user_rank_or_higher(payload.get("sub"), "moderator"):
        raise HTTPException(status_code=403, detail="'moderator' yetkisine sahip değilsiniz.")
    value = req.locked if req is not None else locked
    if value is None:
        raise HTTPException(status_code=400, detail="Missing 'locked' value.")
    global BOARD_LOCKDOWN
    BOARD_LOCKDOWN = bool(value)
    return {"locked": BOARD_LOCKDOWN}


@app.get("/board/last-change")
def get_board_last_change(payload: dict = Depends(get_current_user)):  # auth required
    """Return who last updated the board and when.

    Response fields:
    - updated_by: user id (string) or None
    - updated_by_name: user's display name (or None)
    - updated_at: ISO timestamp string or None
    """
    data = board.load_board()
    updated_by = data.get("updated_by")
    updated_at = data.get("updated_at")
    updated_by_name = None
    if updated_by:
        try:
            user = users.get_user_by_id(updated_by)
            if user:
                updated_by_name = user.get("name")
        except Exception:
            updated_by_name = None
    return {
        "updated_by": updated_by,
        "updated_by_name": updated_by_name,
        "updated_at": updated_at
    }


@app.get("/board")
def get_board():
    return board.load_board()


@app.put("/board")
def update_board(req: BoardUpdateRequest, payload: dict = Depends(get_current_user)):
    user_id = payload.get("sub")
    if not users.check_user_rank_or_higher(user_id, "music"):
        raise HTTPException(status_code=403, detail="'music' yetkisine sahip değilsiniz.")
    ensure_board_edit(payload)
    if req.pinned is not None and not users.check_user_perm(user_id, "admin"):
        raise HTTPException(status_code=403, detail="'admin' yetkisine sahip değilsiniz.")

    # Reload blacklists so changes on disk take effect without restart
    try:
        reload_blacklists()
    except Exception:
        # Fail open if blacklist reload unexpectedly errors; don't block board updates because of IO
        pass

    # Validate user-generated content in incoming widgets
    widgets = req.widgets
    if isinstance(widgets, list):
        for item in widgets:
            if not isinstance(item, dict):
                continue
            wtype = item.get("type") or item.get("id")
            widget_key = item.get("key") or item.get("id") or "<unknown>"
            # Check common title field
            title = item.get("title")
            if isinstance(title, str) and title.strip():
                res = find_blacklist_match(title)
                if res:
                    matched, matched_phrase, rule = res
                    if matched:
                        try:
                            user = users.get_user_by_id(user_id)
                            username = user.get("name") if user else None
                        except Exception:
                            username = None
                        content_logger.info(f"user_id={user_id}\tusername={username}\twidget={widget_key}\tfield=title\tvalue={title!r}\tcontent={matched_phrase!r}\trule={rule}")
                        detail = {
                            "message": "Gönderdiğiniz içerik engellendi.",
                            "rule": matched_phrase,
                            "field": "title",
                            "widget": widget_key,
                            "value": title
                        }
                        raise HTTPException(status_code=400, detail=detail)

            if wtype == "text-block":
                content = item.get("content")
                if isinstance(content, str) and content.strip():
                    res = find_blacklist_match(content)
                    if res:
                        matched, matched_phrase, rule = res
                        if matched:
                            try:
                                user = users.get_user_by_id(user_id)
                                username = user.get("name") if user else None
                            except Exception:
                                username = None
                            content_logger.info(f"user_id={user_id}\tusername={username}\twidget={widget_key}\tfield=content\tvalue={content!r}\tcontent={matched_phrase!r}\trule={rule!r}")
                            detail = {
                                "message": "Gönderdiğiniz içerik engellendi.",
                                "rule": matched_phrase,
                                "field": "content",
                                "widget": widget_key,
                                "value": content
                            }
                            raise HTTPException(status_code=400, detail=detail)

            if wtype == "poll":
                question = item.get("question")
                if isinstance(question, str) and question.strip():
                    res = find_blacklist_match(question)
                    if res:
                        matched, matched_phrase, rule = res
                        if matched:
                            try:
                                user = users.get_user_by_id(user_id)
                                username = user.get("name") if user else None
                            except Exception:
                                username = None
                            content_logger.info(f"user_id={user_id}\tusername={username}\twidget={widget_key}\tfield=question\tvalue={question!r}\tcontent={matched_phrase!r}\treason={rule!r}")
                            detail = {
                                "message": "Gönderdiğiniz içerik engellendi.",
                                "rule": matched_phrase,
                                "field": "question",
                                "widget": widget_key,
                                "value": question
                            }
                            raise HTTPException(status_code=400, detail=detail)
                options = item.get("options") or []
                if isinstance(options, list):
                    for opt in options:
                        if not isinstance(opt, dict):
                            continue
                        label = opt.get("label")
                        opt_id = opt.get("id") or "<no-id>"
                        if isinstance(label, str) and label.strip():
                            res = find_blacklist_match(label)
                            if res:
                                matched, matched_phrase, rule = res
                                if matched:
                                    try:
                                        user = users.get_user_by_id(user_id)
                                        username = user.get("name") if user else None
                                    except Exception:
                                        username = None
                                    content_logger.info(f"user_id={user_id}\tusername={username}\twidget={widget_key}\tfield=poll_option:{opt_id}\tvalue={label!r}\tcontent={matched_phrase!r}\trule={rule}")
                                    detail = {
                                        "message": "Gönderdiğiniz içerik engellendi.",
                                        "rule": matched_phrase,
                                        "field": "poll_option",
                                        "widget": widget_key,
                                        "option_id": opt_id,
                                        "value": label
                                    }
                                    raise HTTPException(status_code=400, detail=detail)

    return board.update_board(
        widgets=req.widgets,
        order_ids=req.order,
        pinned_ids=req.pinned,
        updated_by=user_id,
        theme_key=req.theme_key,
        background_image_url=req.background_image_url,
        background_image_key=req.background_image_key,
        backdrop_blur_px=req.backdrop_blur_px,
        card_blur_px=req.card_blur_px
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
        raise HTTPException(status_code=403, detail="'music' yetkisine sahip değilsiniz.")
    ensure_board_edit(payload)
    config = req.dict(by_alias=True, exclude_none=True)
    trigger = board.set_confetti_trigger(config=config, updated_by=user_id)
    return {"ok": True, "trigger": trigger}


@app.post("/board/redirect")
def trigger_board_redirect(req: BoardRedirectRequest, payload: dict = Depends(get_current_user)):
    user_id = payload.get("sub")
    if not users.check_user_rank_or_higher(user_id, "music"):
        raise HTTPException(status_code=403, detail="'music' yetkisine sahip değilsiniz.")
    ensure_board_edit(payload)
    trigger = board.set_redirect_trigger(path=req.path, updated_by=user_id)
    return {"ok": True, "trigger": trigger}


@app.post("/board/restart")
def trigger_board_restart(payload: dict = Depends(get_current_user)):
    user_id = payload.get("sub")
    if not users.check_user_rank_or_higher(user_id, "music"):
        raise HTTPException(status_code=403, detail="'music' yetkisine sahip değilsiniz.")
    ensure_board_edit(payload)
    trigger = board.set_restart_trigger(updated_by=user_id)
    return {"ok": True, "trigger": trigger}

