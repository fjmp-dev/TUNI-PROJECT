from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError
from typing import Literal, Optional
import uvicorn
import httpx
import asyncio
import os
import re
import json
import glob
import time
import hmac
import hashlib
import secrets
import threading
import yaml

app = FastAPI(title="MIR Suite")

# ============================================================
# Safety: validate any pattern that will be passed to `pkill -f` inside a
# container. Allowed chars cover everything the existing NODES['stop'] and
# freedrive-disable patterns use: alnum, dot, dash, underscore, slash (paths),
# space (with --ports), colon (e.g. /dev/ttyUSB0:left), brackets (the [d]uo_ur_real
# trick that keeps pgrep from matching its own command line), and hyphen.
# Blocked: any shell metacharacter (`;&|<>$()*`"'`#?!~{}`). Defense-in-depth:
# today only NODES['stop'] produces pkill patterns, and those are dev-written.
# This guard ensures that future code that interpolates external data into a
# pkill pattern can't escalate to arbitrary shell execution.
# ============================================================
import logging as _logging
_log = _logging.getLogger("mir_ui")
_PKILL_SAFE = re.compile(r"^[A-Za-z0-9_./ :\[\]-]+$")


def _safe_pkill(container, pattern):
    """Validate `pattern` then run `pkill -f` in `container`. Raises ValueError on
    any unsafe pattern so the caller surfaces a 400/500 instead of executing
    arbitrary shell content. Returns the docker exec result for callers that
    need to inspect exit code / output; other callers can ignore the return."""
    if not isinstance(pattern, str) or not _PKILL_SAFE.match(pattern):
        _log.error("refusing pkill with unsafe pattern: %r", pattern)
        raise ValueError(f"unsafe pkill pattern: {pattern!r}")
    _log.info("pkill in %s: %s", container, pattern)
    return container.exec_run(f"pkill -f '{pattern}'", stdout=True, stderr=True, demux=False)


def _safe_pkill_in(container, pattern):
    """Same as _safe_pkill but discards the return value (fire-and-forget)."""
    _safe_pkill(container, pattern)

# ============================================================
# Configuration (env-overridable; defaults match the lab setup).
# mir_ui loads config/.env via docker-compose `env_file`.
# ============================================================
# Default matches config/.env. It used to say .13 -- an address the MiR has not had
# for a long time -- which meant any deployment without MIR_IP set silently polled a
# dead host. The UI takes the host from /api/mir/status (below) rather than hardcoding
# it a second time, so this stays the single source of truth.
MIR_HOST = os.getenv("MIR_IP", "192.168.1.14")
LEFT_ARM_IP = os.getenv("LEFT_ARM_IP", "192.168.1.102")
RIGHT_ARM_IP = os.getenv("RIGHT_ARM_IP", "192.168.1.103")
MIR_API_BASE = f"http://{MIR_HOST}/api/v2.0.0"
MIR_TIMEOUT = float(os.getenv("MIR_TIMEOUT", "4.0"))          # MiR REST request timeout (s)
MIR_CACHE_TTL = float(os.getenv("MIR_CACHE_TTL", "60.0"))     # serve cached MiR status up to this age (s)

JOINT_SERVER_URL = os.getenv("JOINT_SERVER_URL", "http://localhost:9091/joints")
UR_JOINTS_TTL = float(os.getenv("UR_JOINTS_TTL", "0.1"))      # joints proxy cache (s) -> ~10Hz
UR_MAX_DELTA = float(os.getenv("UR_MAX_DELTA", "0.5"))        # max |delta| per single joint move (rad)
UR_STOP_TIMEOUT = int(os.getenv("UR_STOP_TIMEOUT", "10"))     # ur_stop.sh hard timeout (s)


# ============================================================
# Multi-user profiles + auth.
# Each user is a YAML file /app/data/profiles/<username>.yaml:
#   username, password (pbkdf2), role (user|admin), nodes: [...], settings: {}
# Passwords hashed with stdlib pbkdf2 (no bcrypt -> no aarch64 wheel issues).
# Tokens are in-memory (a mir_ui restart logs everyone out; fine for a LAN tool).
# ============================================================
AUTH_USER = os.getenv("AUTH_USER", "admin")   # only used to seed the initial admin
AUTH_PASS = os.getenv("AUTH_PASS", "admin")
WAEL_PASS = os.getenv("WAEL_PASS", "wael")     # seed user wael, change in production
PABLO_PASS = os.getenv("PABLO_PASS", "pablo")   # seed user pablo, change in production
PROFILES_DIR = os.getenv("PROFILES_DIR", "/app/data/profiles")

_profiles_lock = threading.Lock()
_profiles: dict = {}   # username -> user dict
_tokens: dict = {}     # token -> {"user", "role", "ts"}


def _hash_password(pw: str, salt: bytes = None) -> str:
    salt = salt or secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 200_000)
    return f"pbkdf2_sha256$200000${salt.hex()}${dk.hex()}"


def _verify_password(pw: str, stored: str) -> bool:
    try:
        _algo, iters, salt_hex, hash_hex = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt_hex), int(iters))
        return hmac.compare_digest(dk.hex(), hash_hex)
    except Exception:
        return False


def _save_profile(user: dict) -> None:
    os.makedirs(PROFILES_DIR, exist_ok=True)
    path = os.path.join(PROFILES_DIR, f"{user['username']}.yaml")
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        yaml.safe_dump(user, f, default_flow_style=False, sort_keys=False)
    os.replace(tmp, path)   # atomic


def _load_profiles() -> None:
    _profiles.clear()
    for path in glob.glob(os.path.join(PROFILES_DIR, "*.yaml")):
        try:
            with open(path) as f:
                u = yaml.safe_load(f) or {}
            if u.get("username"):
                u.setdefault("role", "user")
                u.setdefault("nodes", [])
                u.setdefault("settings", {})
                # Migration: profiles written before the can_control capability
                # existed have no such key. Grandfather them in as True so current
                # operators (wael/pablo) keep working, and persist the migration so
                # this only runs once. New users are created with can_control=False
                # (secure default) — an admin grants it explicitly.
                if "can_control" not in u:
                    u["can_control"] = True
                    _profiles[u["username"]] = u
                    _save_profile(u)
                else:
                    _profiles[u["username"]] = u
        except Exception:
            continue


def _seed_profiles() -> None:
    """First run: seed admin (from env) + wael + pablo, all with empty node sets."""
    seeds = (
        ("admin", AUTH_PASS, "admin"),
        ("wael", WAEL_PASS, "user"),
        ("pablo", PABLO_PASS, "user"),
    )
    for username, pw, role in seeds:
        if username not in _profiles:
            # Seed accounts (admin + the two operators) get can_control=True so a
            # fresh install is operable out of the box. admin is allowed regardless.
            _profiles[username] = {"username": username, "password": _hash_password(pw),
                                   "role": role, "nodes": [], "settings": {},
                                   "can_control": True}
            _save_profile(_profiles[username])
    _log_default_passwords(seeds)


def _log_default_passwords(seeds):
    """Warn once at boot if any seed account still uses its factory password."""
    factory_defaults = {"admin": "admin", "wael": "wael", "pablo": "pablo"}
    env_pass_by_user = {
        "admin": os.getenv("AUTH_PASS", "admin"),
        "wael":  os.getenv("WAEL_PASS", "wael"),
        "pablo": os.getenv("PABLO_PASS", "pablo"),
    }
    bad = [u for (u, pw, _role) in seeds if env_pass_by_user.get(u) == factory_defaults.get(u)]
    if bad:
        import logging
        logging.getLogger("mir_ui").warning(
            "DEFAULT SEED PASSWORDS IN USE for: %s. "
            "Override AUTH_PASS/WAEL_PASS/PABLO_PASS in config/.env before production.",
            ", ".join(bad),
        )


with _profiles_lock:
    _load_profiles()
    _seed_profiles()


# Tokens expire after TOKEN_TTL seconds. _resolve_token evicts expired entries
# lazily on access; _token_cleanup_task runs every hour to evict long-idle
# tokens (memory hygiene: prevents _tokens from growing unbounded).
# Configurable in config/.env (TOKEN_TTL, default 24h).
TOKEN_TTL = int(os.getenv("TOKEN_TTL", "86400"))


def _issue_token(username: str, role: str) -> str:
    t = secrets.token_urlsafe(32)
    _tokens[t] = {"user": username, "role": role, "ts": time.time(),
                  "expires": time.time() + TOKEN_TTL}
    return t


def _resolve_token(t):
    if not t:
        return None
    sess = _tokens.get(t)
    if sess is None:
        return None
    if time.time() > sess.get("expires", 0):
        # Expired — evict and reject. The lazy eviction also prevents a tight
        # retry loop from re-evicting every time (pop is idempotent).
        _tokens.pop(t, None)
        return None
    return sess


async def _token_cleanup_task():
    """Hourly background sweep: drop expired tokens. The lazy eviction in
    _resolve_token catches tokens on access, but idle tokens (user logged in
    then closed the browser) would otherwise pile up forever."""
    while True:
        try:
            await asyncio.sleep(3600)
            now = time.time()
            expired = [k for k, v in list(_tokens.items()) if now > v.get("expires", 0)]
            for k in expired:
                _tokens.pop(k, None)
            if expired:
                _log.info("token cleanup: removed %d expired token(s)", len(expired))
        except asyncio.CancelledError:
            return
        except Exception as e:
            _log.warning("token cleanup error: %s", e)


def _public_profile(user: dict) -> dict:
    return {"username": user["username"], "role": user.get("role", "user"),
            "can_control": bool(user.get("can_control", False)),
            "config": {"nodes": user.get("nodes", []), "settings": user.get("settings", {})}}


def _can_control(username: str, role: str) -> bool:
    """Admins may always actuate. A non-admin needs an explicit can_control flag
    on their profile (default False for newly created users)."""
    if role == "admin":
        return True
    user = _profiles.get(username)
    return bool(user and user.get("can_control", False))


@app.middleware("http")
async def _auth_gate(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/") and path != "/api/login":
        sess = _resolve_token(request.headers.get("X-MIR-Token"))
        if sess is None:
            return JSONResponse({"detail": "unauthorized"}, status_code=401)
        request.state.user = sess["user"]
        request.state.role = sess["role"]
    return await call_next(request)


def _require_admin(request: Request):
    if getattr(request.state, "role", None) != "admin":
        raise HTTPException(403, "admin only")


def _require_control(request: Request):
    """Gate for endpoints that actuate hardware (move arms, start/stop the driver,
    launch/stop nodes, start/stop containers). Admin always passes; a plain user
    needs can_control=True on their profile. Read-only endpoints (status, joints,
    camera feed, logs) stay open to any authenticated user."""
    user = getattr(request.state, "user", None)
    role = getattr(request.state, "role", None)
    if not _can_control(user, role):
        raise HTTPException(403, "control not allowed for this user")


class LoginRequest(BaseModel):
    username: str
    password: str


class ConfigRequest(BaseModel):
    nodes: list[str] = []
    settings: dict = {}


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: Literal["user", "admin"] = "user"
    # Secure default: new users cannot actuate the robot until an admin grants it.
    can_control: bool = False


@app.post("/api/login")
async def login(body: LoginRequest):
    user = _profiles.get(body.username)
    if user and _verify_password(body.password, user["password"]):
        token = _issue_token(user["username"], user.get("role", "user"))
        return {"token": token, **_public_profile(user)}
    raise HTTPException(401, "invalid credentials")


@app.post("/api/logout")
async def logout(request: Request):
    _tokens.pop(request.headers.get("X-MIR-Token"), None)
    return {"status": "ok"}


@app.get("/api/me")
async def me(request: Request):
    user = _profiles.get(request.state.user)
    if not user:
        raise HTTPException(404, "profile not found")
    return _public_profile(user)


@app.put("/api/me/config")
async def save_my_config(body: ConfigRequest, request: Request):
    with _profiles_lock:
        user = _profiles.get(request.state.user)
        if not user:
            raise HTTPException(404, "profile not found")
        user["nodes"] = [n for n in body.nodes if n in NODES]
        user["settings"] = dict(body.settings)
        _save_profile(user)
    return _public_profile(user)


@app.post("/api/me/apply")
async def apply_my_nodes(request: Request):
    """Start every node in the current user's saved config (auto-start on login)."""
    _require_control(request)
    user = _profiles.get(request.state.user)
    if not user:
        raise HTTPException(404, "profile not found")
    started, skipped, errors = [], [], []
    for node_id in user.get("nodes", []):
        if node_id not in NODES:
            continue
        # Recording must never start as a side effect of logging in. The rosbag node
        # was saved in admin's profile, so every login silently began recording every
        # topic -- that is how 522 GB landed on the disk on 2026-07-13. Nodes flagged
        # no_autostart are startable only by an explicit click.
        if NODES[node_id].get("no_autostart"):
            skipped.append(node_id)
            continue
        try:
            await asyncio.to_thread(_node_start, node_id)
            started.append(node_id)
        except Exception as e:
            errors.append({"node": node_id, "error": str(e)})
    return {"status": "ok", "started": started, "skipped": skipped, "errors": errors}


@app.get("/api/users")
async def list_users(request: Request):
    _require_admin(request)
    return {"users": [{"username": u["username"], "role": u.get("role", "user"),
                       "can_control": bool(u.get("can_control", False))}
                      for u in _profiles.values()]}


@app.post("/api/users")
async def create_user(body: CreateUserRequest, request: Request):
    _require_admin(request)
    uname = body.username.strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,32}", uname):
        raise HTTPException(422, "invalid username (allowed: A-Z a-z 0-9 _ . -)")
    with _profiles_lock:
        if uname in _profiles:
            raise HTTPException(409, "user already exists")
        user = {"username": uname, "password": _hash_password(body.password),
                "role": body.role, "nodes": [], "settings": {},
                "can_control": bool(body.can_control)}
        _profiles[uname] = user
        _save_profile(user)
    return {"status": "ok", "username": uname, "role": body.role,
            "can_control": bool(body.can_control)}


class UpdateUserRequest(BaseModel):
    role: Optional[str] = None
    password: Optional[str] = None
    can_control: Optional[bool] = None


@app.put("/api/users/{username}")
async def update_user(username: str, body: UpdateUserRequest, request: Request):
    _require_admin(request)
    with _profiles_lock:
        if username not in _profiles:
            raise HTTPException(404, "user not found")
        user = _profiles[username]
        if body.role is not None:
            if body.role not in ("admin", "user"):
                raise HTTPException(422, "role must be 'admin' or 'user'")
            user["role"] = body.role
        if body.password is not None:
            user["password"] = _hash_password(body.password)
        if body.can_control is not None:
            user["can_control"] = bool(body.can_control)
        _save_profile(user)
    return {"status": "ok", "username": username, "role": user["role"],
            "can_control": bool(user.get("can_control", False))}


@app.delete("/api/users/{username}")
async def delete_user(username: str, request: Request):
    _require_admin(request)
    with _profiles_lock:
        if username not in _profiles:
            raise HTTPException(404, "user not found")
        if username == request.state.user:
            raise HTTPException(400, "cannot delete yourself")
        del _profiles[username]
        _profiles_path = Path(__file__).parent / "data" / "profiles"
        user_file = _profiles_path / f"{username}.yaml"
        if user_file.exists():
            user_file.unlink()
    return {"status": "ok", "username": username}

# ============================================================
# Docker service management (requires /var/run/docker.sock)
# ============================================================
try:
    import docker
    docker_client = docker.from_env()
except Exception:
    docker_client = None


# Each UR container declares its own identity via UR_CONTAINER env var (set in
# docker-compose.yml). The backend uses it verbatim — no autodetection, no
# hardcoded priority. This makes the system predictable: the container that
# is running and declares itself is the one that gets used. If neither is
# running, we default to "mir_ur_driver" (the real one) and let the API
# surface a clear "container not running" error.
UR_CONTAINER = os.environ.get("UR_CONTAINER", "mir_ur_driver")


def _ur_container_name() -> str:
    if docker_client is not None:
        for name in ["mir_ur_driver", "mir_ur_driver_sim"]:
            try:
                c = docker_client.containers.get(name)
                if c.status == "running":
                    return name
            except Exception:
                pass
    return UR_CONTAINER

MIR_SERVICES = {
    "mir_ui":       {"label": "Web UI",        "profiles": ["always"]},
    "mir_mir":      {"label": "MiR Bridge",     "profiles": ["always"]},
    "mir_camera":   {"label": "Camera",         "profiles": ["vision", "full"]},
    "mir_ur_driver":     {"label": "UR5e Driver (real)", "profiles": ["arms", "full"]},
    "mir_ur_driver_sim": {"label": "UR5e Driver (sim)",  "profiles": ["sim"]},
}

@app.get("/api/containers")
def list_containers():
    if docker_client is None:
        raise HTTPException(503, "Docker not available")

    containers = docker_client.containers.list(all=True)
    result = []
    for svc_name, meta in MIR_SERVICES.items():
        container = next((c for c in containers if c.name == svc_name), None)
        
        # Add connection status for mir_mir (MiR Bridge)
        extra_info = {}
        if svc_name == "mir_mir" and container and container.status == "running":
            # Check if MiR is reachable
            try:
                import subprocess
                ping_result = subprocess.run(
                    ["ping", "-c", "1", "-W", "1", MIR_HOST],
                    capture_output=True,
                    timeout=2
                )
                extra_info["mir_reachable"] = ping_result.returncode == 0
            except Exception:
                extra_info["mir_reachable"] = False
        
        result.append({
            "name": svc_name,
            "label": meta["label"],
            "profiles": meta["profiles"],
            "running": container.status == "running" if container else False,
            "exists": container is not None,
            "status": container.status if container else "not created",
            **extra_info,
        })
    return {"services": result}


@app.post("/api/containers/{name}/start")
def start_container(name: str, request: Request):
    _require_control(request)
    if docker_client is None:
        raise HTTPException(503, "Docker not available")
    if name not in MIR_SERVICES:
        raise HTTPException(404, f"Unknown service: {name}")

    try:
        container = docker_client.containers.get(name)
        if container.status != "running":
            container.start()
            return {"status": "ok", "action": "started", "name": name}
        return {"status": "ok", "action": "already_running", "name": name}
    except docker.errors.NotFound:
        raise HTTPException(
            404,
            f"Container '{name}' not found. Run 'docker compose --profile <profile> up -d' from the host first."
        )


@app.post("/api/containers/{name}/stop")
def stop_container(name: str, request: Request):
    _require_control(request)
    if docker_client is None:
        raise HTTPException(503, "Docker not available")
    if name not in MIR_SERVICES:
        raise HTTPException(404, f"Unknown service: {name}")

    # Never stop mir_ui itself (would kill the API!)
    if name == "mir_ui":
        raise HTTPException(400, "Cannot stop the UI container itself")

    try:
        container = docker_client.containers.get(name)
        if container.status == "running":
            container.stop()
            return {"status": "ok", "action": "stopped", "name": name}
        return {"status": "ok", "action": "already_stopped", "name": name}
    except docker.errors.NotFound:
        raise HTTPException(404, f"Container '{name}' not found.")


# ============================================================
# UR driver control (start/stop dentro de mir_ur_driver)
# ============================================================
import subprocess as _sp

def _exec_in_ur_driver(script: str, timeout: int = 5) -> tuple[bool, str]:
    if docker_client is None:
        return False, "docker not available"
    try:
        c = docker_client.containers.get(_ur_container_name())
        if c.status != "running":
            return False, f"container not running (status={c.status})"
        r = c.exec_run(f"timeout {timeout} bash {script}", stdout=True, stderr=True, demux=False)
        out = r.output.decode("utf-8", "replace") if isinstance(r.output, bytes) else str(r.output)
        if r.exit_code == 124:
            return False, f"script timed out after {timeout}s: {script}"
        return r.exit_code == 0, out
    except docker.errors.NotFound:
        return False, "container mir_ur_driver not found"
    except Exception as e:
        return False, str(e)


@app.get("/api/ur/status")
def ur_status():
    if docker_client is None:
        raise HTTPException(503, "docker not available")
    try:
        c = docker_client.containers.get(_ur_container_name())
        running = c.status == "running"
    except docker.errors.NotFound:
        return {"container_running": False, "driver_running": False}

    driver_running = False
    if running:
        try:
            r = c.exec_run("bash -c 'pgrep -f [d]uo_ur_real | head -1'", stdout=True, stderr=True, demux=False)
            out = r.output.decode("utf-8", "replace").strip() if isinstance(r.output, bytes) else str(r.output or "").strip()
            driver_running = r.exit_code == 0 and len(out) > 0
        except Exception:
            driver_running = False
    return {"container_running": running, "driver_running": driver_running}


@app.post("/api/ur/start")
def ur_start(request: Request):
    _require_control(request)
    if docker_client is None:
        raise HTTPException(503, "docker not available")
    try:
        c = docker_client.containers.get(_ur_container_name())
        if c.status != "running":
            raise HTTPException(400, "container mir_ur_driver not running")
    except docker.errors.NotFound:
        raise HTTPException(404, "container mir_ur_driver not found")

    # Launch in the background inside the container
    try:
        c.exec_run("nohup bash /ur_start.sh > /var/log/mir/ur_start.log 2>&1 &", detach=True)
    except Exception as e:
        raise HTTPException(500, f"failed to launch ur_start: {e}")
    return {"status": "ok", "action": "starting", "message": "UR driver launching in background"}


@app.post("/api/ur/stop")
def ur_stop(request: Request):
    _require_control(request)
    if docker_client is None:
        raise HTTPException(503, "docker not available")
    try:
        c = docker_client.containers.get(_ur_container_name())
        if c.status != "running":
            raise HTTPException(400, "container mir_ur_driver not running")
    except docker.errors.NotFound:
        raise HTTPException(404, "container mir_ur_driver not found")

    ok, out = _exec_in_ur_driver("/ur_stop.sh", timeout=UR_STOP_TIMEOUT)
    if not ok:
        raise HTTPException(500, f"ur_stop failed: {out}")
    return {"status": "ok", "action": "stopping", "message": out}


class MoveRequest(BaseModel):
    """Validated body for /api/ur/move. Bounds the joint set and the per-move
    delta so a bad/oversized command can never reach the arm."""
    arm: Literal["left", "right"]
    joint: Literal["shoulder_pan", "shoulder_lift", "elbow", "wrist_1", "wrist_2", "wrist_3"]
    delta: float = Field(..., ge=-UR_MAX_DELTA, le=UR_MAX_DELTA)


class PayloadRequest(BaseModel):
    """Validated body for /api/ur/payload. Mass bounded to the UR5e limit (5 kg)
    and CoG to a sane envelope. Setting the payload does not move the arm."""
    arm: Literal["left", "right"]
    mass: float = Field(..., ge=0.0, le=5.0)
    cog_x: float = Field(0.0, ge=-0.5, le=0.5)
    cog_y: float = Field(0.0, ge=-0.5, le=0.5)
    cog_z: float = Field(0.0, ge=-0.5, le=0.5)


class FreedriveRequest(BaseModel):
    """Enable/disable freedrive (hand-guide) on one arm."""
    arm: Literal["left", "right"]
    enable: bool


def _run_freedrive(arm: str, enable: bool) -> dict:
    """Toggle freedrive mode on one arm. Runs in a worker thread.

    Enabling: switch the joint_trajectory_controller out for the
    freedrive_mode_controller, then start a detached publisher that keeps the
    controller's deadman fed (it auto-disengages if publishing stops). Disabling:
    kill that publisher, send a final 'false', and switch the trajectory
    controller back so normal moves work again.
    """
    try:
        c = docker_client.containers.get(_ur_container_name())
    except docker.errors.NotFound:
        raise HTTPException(404, "UR driver container not found")
    if c.status != "running":
        raise HTTPException(400, f"{c.name} not running")

    jtc = f"{arm}_joint_trajectory_controller"
    fd = f"{arm}_freedrive_mode_controller"
    topic = f"/{fd}/enable_freedrive_mode"
    # Bracket trick so pkill doesn't match its own command line.
    kill_pat = f"[{arm[0]}]{arm[1:]}_freedrive_mode_controller/enable"

    def sh(cmd, detach=False):
        full = f"source /opt/ros/humble/setup.bash && {cmd}"
        r = c.exec_run(["bash", "-c", full], stdout=True, stderr=True, detach=detach)
        if detach:
            return 0, ""
        out = (r.output or b"").decode("utf-8", "replace") if isinstance(r.output, bytes) else str(r.output or "")
        return r.exit_code, out

    if enable:
        code, out = sh(f"timeout 10 ros2 control switch_controllers --deactivate {jtc} --activate {fd}")
        if code != 0:
            raise HTTPException(500, f"could not switch to freedrive: {out[:200]}")
        # Keep the deadman fed at 10 Hz (detached).
        sh(f"nohup ros2 topic pub -r 10 {topic} std_msgs/msg/Bool '{{data: true}}' "
           f">/var/log/mir/freedrive_{arm}.log 2>&1 &", detach=True)
        return {"status": "ok", "arm": arm, "freedrive": True}

    # disable
    _safe_pkill_in(c, kill_pat)
    sh(f"timeout 3 ros2 topic pub -1 {topic} std_msgs/msg/Bool '{{data: false}}'")
    code, out = sh(f"timeout 10 ros2 control switch_controllers --deactivate {fd} --activate {jtc}")
    if code != 0:
        raise HTTPException(500, f"freedrive off but could not restore trajectory controller: {out[:200]}")
    return {"status": "ok", "arm": arm, "freedrive": False}


def _run_set_payload(arm: str, mass: float, cx: float, cy: float, cz: float) -> dict:
    """Set the arm payload via the UR set_payload service. Runs in a worker thread
    (no event-loop block). No motion is commanded."""
    try:
        c = docker_client.containers.get(_ur_container_name())
    except docker.errors.NotFound:
        raise HTTPException(404, "UR driver container not found")
    if c.status != "running":
        raise HTTPException(400, f"{c.name} not running")

    srv = f"/{arm}_io_and_status_controller/set_payload"
    body = f"{{mass: {mass}, center_of_gravity: {{x: {cx}, y: {cy}, z: {cz}}}}}"
    cmd = (
        "bash -c 'source /opt/ros/humble/setup.bash && "
        f'ros2 service call {srv} ur_msgs/srv/SetPayload "{body}"\''
    )
    try:
        r = c.exec_run(cmd, stdout=True, stderr=True, demux=False)
        out = (r.output or b"").decode("utf-8", "replace") if isinstance(r.output, bytes) else str(r.output or "")
    except Exception as e:
        raise HTTPException(500, f"exec failed: {e}")

    if r.exit_code != 0 or "success=True" not in out.replace(" ", ""):
        raise HTTPException(500, f"set_payload failed: {out[:300]}")
    return {"status": "ok", "arm": arm, "mass": mass, "cog": [cx, cy, cz]}


def _run_move(arm: str, joint: str, delta: float) -> dict:
    """Blocking joint move via docker exec. Runs in a worker thread (see ur_move)
    so the long-running exec never blocks the asyncio event loop — otherwise the
    whole API, joint polling included, would freeze for the duration of a move."""
    try:
        c = docker_client.containers.get(_ur_container_name())
    except docker.errors.NotFound:
        raise HTTPException(404, "UR driver container not found")
    if c.status != "running":
        raise HTTPException(400, f"{c.name} not running")

    move_script = (
        "source /opt/ros/humble/setup.bash && "
        "source /root/workspace/ros_ws/install/setup.bash 2>/dev/null && "
        f"python3 /joint_mover.py {arm} {joint} {delta}"
    )
    cmd = ["bash", "-c", move_script]
    try:
        r = c.exec_run(cmd, stdout=True, stderr=True, demux=False)
        out = (r.output or b"").decode("utf-8", "replace") if isinstance(r.output, bytes) else str(r.output or "")
    except Exception as e:
        raise HTTPException(500, f"exec failed: {e}")

    # If it failed with a recoverable error, attempt recovery: resend robot program
    # + reactivate controller. Covers the typical failure modes of the controller_stopper /
    # dropped external program: goal rejected, controller inactive, or timeout.
    _low = out.lower()
    _recoverable = any(s in _low for s in ("goal rejected", "controller not available", "timeout waiting", "no motion"))
    if r.exit_code != 0 and _recoverable:
        # NOTE: must go through docker-py (exec_run) like every other exec in this
        # file — the mir_ui image has no `docker` CLI, so subprocess["docker",...]
        # raised FileNotFoundError and surfaced as a bare 500 without ever running
        # the recovery. The sleep gives the External Control program ~2s to
        # reconnect the reverse interface after the resend before we retry.
        recovery_script = (
            "source /opt/ros/humble/setup.bash && "
            "source /root/workspace/ros_ws/install/setup.bash 2>/dev/null; "
            f"ros2 service call /{arm}_io_and_status_controller/resend_robot_program std_srvs/srv/Trigger '{{}}' >/dev/null 2>&1 && "
            f"sleep 3 && "
            f"ros2 control switch_controllers --activate {arm}_joint_trajectory_controller >/dev/null 2>&1"
        )
        try:
            c.exec_run(["bash", "-c", recovery_script], stdout=True, stderr=True, demux=False)
        except Exception:
            pass  # recovery is best-effort; fall through to the informative 500
        # Reintentar
        try:
            r2 = c.exec_run(cmd, stdout=True, stderr=True, demux=False)
            out2 = (r2.output or b"").decode("utf-8", "replace") if isinstance(r2.output, bytes) else str(r2.output or "")
            if r2.exit_code == 0:
                return {"status": "ok", "arm": arm, "joint": joint, "delta": delta,
                        "message": out2.strip(), "recovered": True}
            out = out2
        except Exception:
            pass

    if r.exit_code != 0:
        raise HTTPException(500, f"joint_mover failed (exit {r.exit_code}): {out[:300]}")
    return {"status": "ok", "arm": arm, "joint": joint, "delta": delta, "message": out.strip()}


@app.post("/api/ur/move")
async def ur_move(req: Request):
    _require_control(req)
    raw = await req.body()
    sanitized = re.sub(r':\s*\+', ': ', raw.decode("utf-8"))
    try:
        move = MoveRequest.model_validate_json(sanitized)
    except ValidationError as e:
        raise HTTPException(422, f"invalid move request: {e.errors()}")
    if docker_client is None:
        raise HTTPException(503, "docker not available")
    return await asyncio.to_thread(_run_move, move.arm, move.joint, move.delta)


@app.post("/api/ur/payload")
async def ur_payload(body: PayloadRequest, request: Request):
    _require_control(request)
    if docker_client is None:
        raise HTTPException(503, "docker not available")
    return await asyncio.to_thread(
        _run_set_payload, body.arm, body.mass, body.cog_x, body.cog_y, body.cog_z
    )


@app.post("/api/ur/freedrive")
async def ur_freedrive(body: FreedriveRequest, request: Request):
    _require_control(request)
    if docker_client is None:
        raise HTTPException(503, "docker not available")
    return await asyncio.to_thread(_run_freedrive, body.arm, body.enable)


# ============================================================
# Node launcher — individual ROS nodes/processes (data-driven registry).
# Container-level control is /api/containers/*; this is per-node inside a container.
# ============================================================
# start_cmd is the BARE command; _node_start wraps it with a bash -c that sources
# ROS + the workspace overlay, nohup-backgrounds it, and redirects to `log`.
NODES = {
    "ur_driver": {
        "label": "UR5e Driver (duo_ur)",
        "desc": ("Connects to both UR5e arms over RTDE and brings up ros2_control, so the "
                 "arms can be jogged from the Arms tab. Nothing moves on its own: it only "
                 "makes the arms controllable. Needs the arms powered on."),
        "container": _ur_container_name,
        "pgrep": "[d]uo_ur_real",
        "start_cmd": "bash /ur_start.sh",
        "log": "/var/log/mir/ur_start.log",
        "stop": {"kind": "script", "path": "/ur_stop.sh", "timeout": UR_STOP_TIMEOUT},
    },
    "hand_real": {
        "label": "Hand Control (real)",
        "desc": ("Drives the two BrainCo Revo1 hands over USB serial. Finger currents are "
                 "clamped in software. Requires the hands plugged in and powered."),
        "container": _ur_container_name,
        "pgrep": "[h]and_control_node.py --ports",
        "start_cmd": "python3 /hand_control_node.py --ports /dev/ttyUSB0:left /dev/ttyUSB1:right",
        "log": "/var/log/mir/hand_control.log",
        "stop": {"kind": "pkill", "pattern": "hand_control_node.py --ports"},
    },
    # Mock variant: logs commands + cycles a demo open/close, no hardware/SDK.
    "hand_mock": {
        "label": "Hand Control (mock)",
        "desc": ("Same hand node with no hardware: it logs the commands it would send and "
                 "cycles a demo open/close. Use it to exercise the UI without the hands."),
        "container": _ur_container_name,
        "pgrep": "[h]and_control_node.py --mock",
        "start_cmd": "python3 /hand_control_node.py --mock",
        "log": "/var/log/mir/hand_mock.log",
        "stop": {"kind": "pkill", "pattern": "hand_control_node.py --mock"},
    },
    "rosbag": {
        "label": "Record rosbag (10 min max, no raw images)",
        "desc": ("Records the ROS topics to a file on disk for later replay. WRITES A LOT OF "
                 "DATA: it stops itself after 10 minutes and skips raw/depth images, because "
                 "an unbounded recording once wrote 522 GB and filled the disk. Stop it as "
                 "soon as you have what you need."),
        "container": _ur_container_name,
        "pgrep": "[r]os2 bag record",
        # Explicit click only -- never auto-started from a saved profile. See
        # /api/me/apply for the incident this prevents.
        "no_autostart": True,
        # BOUNDED ON PURPOSE. The old command was a bare `ros2 bag record -a`: every
        # topic, no size cap, no time cap. Started from the UI on 2026-07-13 it wrote
        # 522 GB in three hours (the camera alone is ~30 Hz of images), filled the
        # 937 GB root disk, and died mid-write -- leaving a bag with no metadata.yaml,
        # i.e. unreadable. A recording that kills the host is not a feature.
        #   timeout 600  -> SIGTERM after 10 min, which closes the bag cleanly.
        #   -x           -> drop the firehose topics (raw/depth images, point clouds).
        #                   The compressed camera stream is still recorded.
        #   --max-bag-size -> split into 2 GB files so a crash costs one file, not all.
        # $(date ...) is evaluated by the bash -c wrapper -> a fresh timestamped bag each run.
        "start_cmd": (
            "timeout --signal=TERM 600 "
            "ros2 bag record -a "
            "-x '.*/image_raw$|.*/depth/.*|.*/points.*|.*/depth_registered/.*' "
            "--max-bag-size 2000000000 "
            "-o /var/log/mir/bag_$(date +%Y%m%d_%H%M%S)"
        ),
        "log": "/var/log/mir/rosbag.log",
        "stop": {"kind": "pkill", "pattern": "ros2 bag record"},  # SIGTERM closes the bag cleanly
    },
    # Camera is on-demand (single USB device -> two mutually-exclusive variants).
    # pgrep keys on the enable_depth arg so status tells color vs depth apart.
    "camera_color": {
        "label": "Camera (color)",
        "desc": ("Orbbec Gemini 335Lg, colour stream only (480x270 @ 30 fps) — this is what "
                 "the Camera tab shows. Cheapest option; cannot run at the same time as the "
                 "depth variant (one USB device)."),
        "container": "mir_camera",
        "pgrep": "[e]nable_depth:=false",
        "start_cmd": ("ros2 launch orbbec_camera gemini_330_series.launch.py "
                      "color_width:=480 color_height:=270 color_fps:=30 time_domain:=device enable_depth:=false"),
        "log": "/var/log/mir/camera.log",
        "stop": {"kind": "pkill", "pattern": "orbbec"},
    },
    "camera_depth": {
        "label": "Camera (color + depth + cloud)",
        "desc": ("Same camera with depth and a coloured point cloud on top — what you want for "
                 "perception/grasping. Heavier on USB and CPU than the colour-only variant, and "
                 "mutually exclusive with it."),
        "container": "mir_camera",
        "pgrep": "[e]nable_depth:=true",
        "start_cmd": ("ros2 launch orbbec_camera gemini_330_series.launch.py "
                      "color_width:=480 color_height:=270 color_fps:=30 time_domain:=device "
                      "enable_depth:=true depth_registration:=true enable_colored_point_cloud:=true"),
        "log": "/var/log/mir/camera.log",
        "stop": {"kind": "pkill", "pattern": "orbbec"},
    },
}


# Read-only infrastructure processes (started at container boot; shown as status
# only — no start/stop, since the UI depends on them / a watchdog owns them).
SYSTEM = {
    "rosbridge": {
        "label": "rosbridge (:9090)", "container": _ur_container_name, "pgrep": "[r]osbridge_websocket",
        "desc": ("The bridge this web page talks to for live data (camera, joints). Read-only: "
                 "it can only subscribe to whitelisted topics, never command the robot."),
    },
    "joint_server": {
        "label": "Joint server", "container": _ur_container_name, "pgrep": "[j]oint_server.py",
        "desc": "Publishes the arms' joint positions to the UI. Loopback only, not exposed to the LAN.",
    },
    "action_bridge": {
        "label": "Action bridge", "container": _ur_container_name, "pgrep": "[a]ction_bridge.py",
        "desc": "Turns the UI's skill requests (grasp, move to pose, hand open/close) into ROS actions.",
    },
    "mir_bridge": {
        "label": "MiR bridge", "container": "mir_mir",
        # Was "[m]ir_raw.py" -- that script was deleted when Wael's selective bridge
        # replaced it, so this always reported "stopped" even while the bridge ran.
        "pgrep": "[m]ir_bridge.py",
        "desc": ("Bridges the MiR200's own ROS with ours: odometry, both laser scanners and "
                 "battery in, /cmd_vel out. Restarts itself if the MiR drops off the network."),
    },
}


def _node_container(node: dict) -> str:
    cn = node["container"]
    return cn() if callable(cn) else cn


def _pgrep(container_name: str, pattern: str) -> bool:
    """True if a process matching `pattern` is running in `container_name`."""
    if docker_client is None:
        return False
    try:
        c = docker_client.containers.get(container_name)
        if c.status != "running":
            return False
        r = c.exec_run(f"bash -c 'pgrep -f \"{pattern}\" | head -1'", stdout=True, stderr=True, demux=False)
        out = r.output.decode("utf-8", "replace").strip() if isinstance(r.output, bytes) else str(r.output or "").strip()
        return r.exit_code == 0 and len(out) > 0
    except Exception:
        return False


# Per-node-id start/stop locks. Prevents the TOCTOU race where two concurrent
# clicks (or two overlapping apply-my-nodes calls) both see "not running",
# both spawn the process, and end up with two of them. Each node gets its own
# lock so unrelated nodes don't serialize. The lock is held for the duration
# of the pgrep-check + exec_run-spawn — i.e. a few hundred ms at most. This
# is the Python-side guard; ur_start.sh also has a flock for defense in depth
# (protects against SSH/manual invocation racing the backend).
_node_locks: dict = {}
_node_locks_lock = threading.Lock()


def _get_node_lock(node_id: str) -> threading.Lock:
    with _node_locks_lock:
        if node_id not in _node_locks:
            _node_locks[node_id] = threading.Lock()
        return _node_locks[node_id]


def _node_status(node_id: str) -> bool:
    node = NODES[node_id]
    return _pgrep(_node_container(node), node["pgrep"])


def _node_start(node_id: str) -> bool:
    node = NODES[node_id]
    if docker_client is None:
        raise HTTPException(503, "docker not available")
    # Per-node lock prevents two concurrent /api/nodes/{id}/start calls (e.g. a
    # double-click) from both passing the pgrep "not running" check and both
    # spawning the process. Held only for the duration of the check + spawn,
    # never across a blocking call.
    with _get_node_lock(node_id):
        return _node_start_locked(node_id, node)


def _node_start_locked(node_id: str, node: dict) -> bool:
    c = docker_client.containers.get(_node_container(node))
    if c.status != "running":
        raise HTTPException(400, f"{c.name} not running")
    # Idempotent: don't spawn a duplicate if it's already running (auto-start on
    # login can fire repeatedly; ur_start.sh self-guards, the node scripts do not).
    r = c.exec_run(f"bash -c 'pgrep -f \"{node['pgrep']}\" | head -1'", stdout=True, stderr=True, demux=False)
    out = r.output.decode("utf-8", "replace").strip() if isinstance(r.output, bytes) else str(r.output or "").strip()
    if r.exit_code == 0 and out:
        return True
    # List-form bash -c guarantees the redirect/& and ROS sourcing are interpreted
    # (a string cmd would NOT go through a shell — args leak to the program).
    log = node.get("log", f"/var/log/mir/{node_id}.log")
    full = ("source /opt/ros/humble/setup.bash && "
            "source /root/workspace/ros_ws/install/setup.bash 2>/dev/null && "
            f"nohup {node['start_cmd']} > {log} 2>&1 &")
    c.exec_run(["bash", "-c", full], detach=True)
    return True


def _node_stop(node_id: str) -> bool:
    node = NODES[node_id]
    if docker_client is None:
        raise HTTPException(503, "docker not available")
    # Same per-node lock as _node_start: prevents start/stop races (e.g. a
    # stop issued while a start is in flight).
    with _get_node_lock(node_id):
        return _node_stop_locked(node_id, node)


def _node_stop_locked(node_id: str, node: dict) -> bool:
    c = docker_client.containers.get(_node_container(node))
    if c.status != "running":
        raise HTTPException(400, f"{c.name} not running")
    stop = node["stop"]
    if stop["kind"] == "script":
        c.exec_run(f"timeout {stop.get('timeout', 10)} bash {stop['path']}", stdout=True, stderr=True)
    else:
        try:
            _safe_pkill(c, stop["pattern"])
        except ValueError as ve:
            raise HTTPException(500, str(ve))
    return True


@app.get("/api/nodes")
async def list_nodes():
    result = []
    for node_id, node in NODES.items():
        running = await asyncio.to_thread(_node_status, node_id)
        result.append({"id": node_id, "label": node["label"],
                       "desc": node.get("desc", ""),
                       "no_autostart": bool(node.get("no_autostart")),
                       "container": _node_container(node), "running": running})
    return {"nodes": result}


@app.get("/api/system")
async def list_system():
    """Read-only status of the always-on infrastructure processes."""
    result = []
    for sid, s in SYSTEM.items():
        cname = s["container"]() if callable(s["container"]) else s["container"]
        running = await asyncio.to_thread(_pgrep, cname, s["pgrep"])
        result.append({"id": sid, "label": s["label"], "desc": s.get("desc", ""), "running": running})
    return {"system": result}


@app.post("/api/nodes/{node_id}/start")
async def node_start_ep(node_id: str, request: Request):
    _require_control(request)
    if node_id not in NODES:
        raise HTTPException(404, f"unknown node: {node_id}")
    await asyncio.to_thread(_node_start, node_id)
    return {"status": "ok", "action": "starting", "id": node_id}


@app.post("/api/nodes/{node_id}/stop")
async def node_stop_ep(node_id: str, request: Request):
    _require_control(request)
    if node_id not in NODES:
        raise HTTPException(404, f"unknown node: {node_id}")
    await asyncio.to_thread(_node_stop, node_id)
    return {"status": "ok", "action": "stopping", "id": node_id}


def _node_tail(node_id: str, lines: int) -> str:
    node = NODES[node_id]
    log = node.get("log", f"/var/log/mir/{node_id}.log")
    if docker_client is None:
        return "docker not available"
    try:
        c = docker_client.containers.get(_node_container(node))
        if c.status != "running":
            return f"(container {c.name} not running)"
        r = c.exec_run(f"bash -c 'tail -n {lines} {log} 2>/dev/null || echo no-log-yet'",
                       stdout=True, stderr=True, demux=False)
        return r.output.decode("utf-8", "replace") if isinstance(r.output, bytes) else str(r.output or "")
    except Exception as e:
        return f"(error reading log: {e})"


@app.get("/api/nodes/{node_id}/logs")
async def node_logs(node_id: str, lines: int = 200):
    if node_id not in NODES:
        raise HTTPException(404, f"unknown node: {node_id}")
    lines = max(1, min(1000, lines))
    text = await asyncio.to_thread(_node_tail, node_id, lines)
    return {"id": node_id, "log": NODES[node_id].get("log"), "text": text}


@app.get("/health")
def health():
    return {"status": "ok", "service": "MIR_Suite"}


# Joints cache to avoid overloading the container (config: UR_JOINTS_TTL, JOINT_SERVER_URL)
_ur_joints_cache = {"data": None, "ts": 0.0}


@app.get("/api/ur/joints")
async def ur_joints():
    global _ur_joints_cache
    now = asyncio.get_event_loop().time()
    if _ur_joints_cache["data"] is not None and (now - _ur_joints_cache["ts"]) < UR_JOINTS_TTL:
        return _ur_joints_cache["data"]

    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            r = await client.get(JOINT_SERVER_URL)
            if r.status_code != 200:
                raise HTTPException(503, f"joint server returned {r.status_code}")
            data = r.json()
    except httpx.TimeoutException:
        raise HTTPException(504, "joint server timeout")
    except httpx.HTTPError as e:
        raise HTTPException(502, f"joint server error: {e}")
    except Exception as e:
        raise HTTPException(500, f"proxy error: {e}")

    if "error" in data:
        raise HTTPException(503, data["error"])

    _ur_joints_cache = {"data": data, "ts": now}
    return data


_mir_cache = {"data": None, "ts": 0.0}  # config: MIR_CACHE_TTL


@app.get("/api/config")
async def get_config():
    """Addresses the UI displays. Served from here so the IPs live in exactly one
    place (config/.env): MirPanel used to print a hardcoded 192.168.1.13, an address
    the MiR no longer has, so the panel confidently named the wrong robot."""
    return {"mir_ip": MIR_HOST, "left_arm_ip": LEFT_ARM_IP, "right_arm_ip": RIGHT_ARM_IP}


@app.get("/api/mir/status")
async def mir_status():
    global _mir_cache
    try:
        async with httpx.AsyncClient(timeout=MIR_TIMEOUT) as client:
            r = await client.get(f"{MIR_API_BASE}/status")
            r.raise_for_status()
            data = r.json()
        _mir_cache = {"data": data, "ts": asyncio.get_event_loop().time()}
    except (httpx.TimeoutException, httpx.HTTPError) as e:
        now = asyncio.get_event_loop().time()
        age = now - _mir_cache["ts"]
        if _mir_cache["data"] is not None and age < MIR_CACHE_TTL:
            return {**_format_mir_status(_mir_cache["data"]), "stale": True, "age_s": int(age)}
        detail = "timeout" if isinstance(e, httpx.TimeoutException) else f"http error: {e}"
        raise HTTPException(504, f"MiR {detail} (no cached data)")
    except Exception as e:
        raise HTTPException(500, f"MiR proxy error: {e}")

    return _format_mir_status(data)


def _format_mir_status(data):
    pos = data.get("position", {})
    vel = data.get("velocity", {})
    return {
        "ok": True,
        "state": data.get("state_text", "Unknown"),
        "mode": data.get("mode_text", "Unknown"),
        "mission": data.get("mission_text", ""),
        "battery_pct": data.get("battery_percentage", 0.0),
        "battery_time_s": data.get("battery_time_remaining", 0),
        "position": {
            "x": pos.get("x", 0.0),
            "y": pos.get("y", 0.0),
            "orientation": pos.get("orientation", 0.0),
        },
        "velocity": {
            "linear": vel.get("linear", 0.0),
            "angular": vel.get("angular", 0.0),
        },
        "errors": data.get("errors", []),
        "uptime_s": data.get("uptime", 0),
        "distance_to_target": data.get("distance_to_next_target", 0.0),
        "robot_name": data.get("robot_name", ""),
        "map_id": data.get("map_id", ""),
    }



# ============================================================
# In-UI terminal — a WebSocket bridged to an interactive `docker exec bash` (tty).
# The http auth middleware does NOT run for websockets, so we auth here via a
# query-param token (WS handshakes can't set the X-MIR-Token header). Full shell +
# docker.sock ~= host root, so gate to admin. UI is login-gated on a local network.
# ============================================================
TERM_ALLOWED = {"mir_ur_driver", "mir_ur_driver_sim", "mir_mir", "mir_camera"}


@app.websocket("/api/term")
async def term_ws(ws: WebSocket):
    sess = _resolve_token(ws.query_params.get("token"))
    if sess is None or sess.get("role") != "admin":
        await ws.close(code=4401)
        return
    cname = ws.query_params.get("container") or _ur_container_name()
    if cname not in TERM_ALLOWED:
        await ws.close(code=4404)
        return
    if docker_client is None:
        await ws.close(code=4503)
        return
    await ws.accept()
    api = docker_client.api
    try:
        # Source ROS before handing over the shell: none of the images put ros2 on
        # PATH by default, so a bare `bash` gives "ros2: command not found" and the
        # terminal looks broken. `exec bash` keeps it interactive (and the exported
        # env survives into it). The overlay is best-effort -- mir_camera/mir_mir
        # have no ros_ws build, hence the 2>/dev/null.
        shell = (
            "source /opt/ros/humble/setup.bash 2>/dev/null; "
            "source /root/workspace/ros_ws/install/setup.bash 2>/dev/null; "
            "exec bash"
        )
        exec_id = api.exec_create(
            cname, ["bash", "-c", shell], tty=True, stdin=True, stdout=True, stderr=True
        )["Id"]
        sock = api.exec_start(exec_id, socket=True, tty=True)
        raw = sock._sock  # underlying socket for raw read/write
    except Exception as e:
        try:
            await ws.send_text(f"\r\n[failed to open shell in {cname}: {e}]\r\n")
        finally:
            await ws.close()
        return

    async def pump_out():  # container -> browser (blocking recv off the loop)
        try:
            while True:
                data = await asyncio.to_thread(raw.recv, 4096)
                if not data:
                    break
                await ws.send_bytes(data)
        except Exception:
            pass

    out_task = asyncio.create_task(pump_out())
    try:
        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.disconnect":
                break
            if msg.get("bytes") is not None:
                await asyncio.to_thread(raw.sendall, msg["bytes"])
            elif msg.get("text") is not None:
                try:
                    ev = json.loads(msg["text"])
                except Exception:
                    ev = None
                if isinstance(ev, dict) and ev.get("type") == "resize":
                    try:
                        api.exec_resize(exec_id, height=int(ev["rows"]), width=int(ev["cols"]))
                    except Exception:
                        pass
                else:
                    await asyncio.to_thread(raw.sendall, msg["text"].encode())
    except Exception:
        pass
    finally:
        out_task.cancel()
        try:
            raw.close()
        except Exception:
            pass


# ============================================================
# Nordbo force/torque sensors (NRS-ETH, model NRS-6200). OUR OWN reader of the
# sensor's native WebSocket (ws://<ip>:2003): send {"cmd":"START_TRANSMISSION"},
# then read 48-byte binary frames = 6 little-endian doubles [Fx,Fy,Fz,Tx,Ty,Tz].
# (Nordbo's ROS node uses an old TCP protocol this firmware ignores, so we skip it.)
# ============================================================
import struct as _struct
try:
    import websockets as _ws
except Exception:
    _ws = None

NORDBO_SENSORS = {
    "left":  os.getenv("NORDBO_LEFT_IP", "192.168.1.112"),
    "right": os.getenv("NORDBO_RIGHT_IP", "192.168.1.113"),
}
NORDBO_PORT = int(os.getenv("NORDBO_PORT", "2003"))

_force = {side: {"connected": False, "fx": 0.0, "fy": 0.0, "fz": 0.0,
                 "tx": 0.0, "ty": 0.0, "tz": 0.0} for side in NORDBO_SENSORS}
_tare_req = {side: False for side in NORDBO_SENSORS}
# Per-side pause flag: when True, the reader loop sleeps instead of (re)connecting.
# Lets the user open the Nordbo sensor's native web UI (which also needs the
# single WebSocket slot the sensor exposes on :2003). Set/cleared by the
# /api/force/{disconnect,connect} endpoints below.
_nordbo_paused = {side: False for side in NORDBO_SENSORS}
# Reference to the live WebSocket so /api/force/disconnect can close it from
# outside the reader task (the reader otherwise holds the only handle).
_nordbo_ws = {side: None for side in NORDBO_SENSORS}


async def _nordbo_reader(side, ip):
    url = f"ws://{ip}:{NORDBO_PORT}"
    while True:
        if _ws is None:
            await asyncio.sleep(10)
            continue
        if _nordbo_paused[side]:
            await asyncio.sleep(1)
            continue
        try:
            async with _ws.connect(url, open_timeout=5, ping_interval=None) as ws:
                _nordbo_ws[side] = ws
                try:
                    await ws.send('{"cmd": "START_TRANSMISSION"}')
                    _force[side]["connected"] = True
                    async for m in ws:
                        if _tare_req[side]:
                            _tare_req[side] = False
                            try:
                                await ws.send('{"cmd": "DO_TARE"}')
                            except Exception:
                                pass
                        if isinstance(m, (bytes, bytearray)) and len(m) == 48:
                            fx, fy, fz, tx, ty, tz = _struct.unpack("<6d", m)
                            _force[side].update(fx=fx, fy=fy, fz=fz, tx=tx, ty=ty, tz=tz)
                finally:
                    _nordbo_ws[side] = None
        except Exception:
            _force[side]["connected"] = False
            _nordbo_ws[side] = None
            await asyncio.sleep(3)  # reconnect backoff


@app.on_event("startup")
async def _start_nordbo():
    for side, ip in NORDBO_SENSORS.items():
        asyncio.create_task(_nordbo_reader(side, ip))
    # Hourly token cleanup task — drops expired tokens to prevent unbounded
    # growth of the in-memory _tokens dict. Lazy eviction in _resolve_token
    # handles per-request cleanup; this is the bulk sweeper.
    asyncio.create_task(_token_cleanup_task())


@app.get("/api/force")
async def force_status():
    return {"sensors": {side: {**_force[side], "paused": _nordbo_paused[side]}
                         for side in NORDBO_SENSORS}}


@app.post("/api/force/{side}/tare")
async def force_tare(side: str):
    if side not in NORDBO_SENSORS:
        raise HTTPException(404, "unknown sensor")
    _tare_req[side] = True
    return {"status": "ok", "side": side, "action": "tare"}


@app.post("/api/force/{side}/disconnect")
async def force_disconnect(side: str):
    """Pause the Nordbo reader for this side so the sensor's native web UI
    (served on its own IP, port 80) can grab the single WebSocket slot. The
    reader stops reconnecting until /api/force/{side}/connect is called."""
    if side not in NORDBO_SENSORS:
        raise HTTPException(404, "unknown sensor")
    _nordbo_paused[side] = True
    ws = _nordbo_ws.get(side)
    if ws is not None:
        try:
            await ws.close()
        except Exception as exc:
            _log.debug("nordbo %s: close-on-disconnect raised %s", side, exc)
    _force[side]["connected"] = False
    _log.info("nordbo %s: reader paused (native UI can now connect)", side)
    return {"status": "ok", "side": side, "action": "disconnect", "ip": NORDBO_SENSORS[side]}


@app.post("/api/force/{side}/connect")
async def force_connect(side: str):
    """Resume the Nordbo reader for this side. The reader loop wakes on its
    next 1s tick and reconnects."""
    if side not in NORDBO_SENSORS:
        raise HTTPException(404, "unknown sensor")
    _nordbo_paused[side] = False
    _log.info("nordbo %s: reader resumed", side)
    return {"status": "ok", "side": side, "action": "connect"}


app.mount("/", StaticFiles(directory="static", html=True), name="ui")


if __name__ == "__main__":
    # Behind the Caddy TLS proxy, bind loopback only (UI_BIND_HOST=127.0.0.1 in
    # config/.env) so the plaintext HTTP port is NOT reachable from the LAN — only
    # Caddy, on the same host, proxies to it over https. Defaults to 0.0.0.0 so a
    # no-proxy/dev run still works.
    uvicorn.run(app, host=os.getenv("UI_BIND_HOST", "0.0.0.0"),
                port=int(os.getenv("UI_PORT", "8080")))