from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn
import httpx
import asyncio
import json
import os
import re

app = FastAPI(title="MIR Suite")

MIR_HOST = "192.168.1.13"
MIR_API_BASE = f"http://{MIR_HOST}/api/v2.0.0"
MIR_TIMEOUT = 4.0

# ============================================================
# Docker service management (requires /var/run/docker.sock)
# ============================================================
try:
    import docker
    docker_client = docker.from_env()
except Exception:
    docker_client = None

# Which UR driver container the /api/ur/* endpoints target. We auto-detect the
# running one so the same endpoints drive either the real arms (mir_ur_driver)
# or the fake-hardware sim (mir_ur_driver_sim). They are mutually exclusive —
# both bind rosbridge :9090 — so at most one is up. Set UR_CONTAINER to force one.
UR_CONTAINER_OVERRIDE = os.environ.get("UR_CONTAINER")
_UR_CONTAINER_CANDIDATES = ("mir_ur_driver", "mir_ur_driver_sim")


def _ur_container_name() -> str:
    if UR_CONTAINER_OVERRIDE:
        return UR_CONTAINER_OVERRIDE
    if docker_client is not None:
        for name in _UR_CONTAINER_CANDIDATES:
            try:
                if docker_client.containers.get(name).status == "running":
                    return name
            except Exception:
                continue
    return "mir_ur_driver"

MIR_SERVICES = {
    "mir_ui":       {"label": "Web UI",        "profiles": ["always"]},
    "mir_mir":      {"label": "MiR Bridge",     "profiles": ["always"]},
    "mir_camera":   {"label": "Camera",         "profiles": ["vision", "full"]},
    "mir_ur_driver": {"label": "UR5e Driver",   "profiles": ["arms", "full"]},
}

@app.get("/api/containers")
def list_containers():
    if docker_client is None:
        raise HTTPException(503, "Docker not available")

    containers = docker_client.containers.list(all=True)
    result = []
    for svc_name, meta in MIR_SERVICES.items():
        container = next((c for c in containers if c.name == svc_name), None)
        result.append({
            "name": svc_name,
            "label": meta["label"],
            "profiles": meta["profiles"],
            "running": container.status == "running" if container else False,
            "exists": container is not None,
            "status": container.status if container else "not created",
        })
    return {"services": result}


@app.post("/api/containers/{name}/start")
def start_container(name: str):
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
def stop_container(name: str):
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
        r = c.exec_run(f"bash {script}", stdout=True, stderr=True, demux=False)
        out = r.output.decode("utf-8", "replace") if isinstance(r.output, bytes) else str(r.output)
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
            # Bracket trick so pgrep doesn't match its own command line (which
            # literally contains "duo_ur_real"): "[d]uo_ur_real" matches the
            # running launch process but not the pgrep invocation itself.
            r = c.exec_run("bash -c 'pgrep -f [d]uo_ur_real | head -1'", stdout=True, stderr=True, demux=False)
            out = r.output.decode("utf-8", "replace").strip() if isinstance(r.output, bytes) else str(r.output or "").strip()
            driver_running = r.exit_code == 0 and len(out) > 0
        except Exception:
            driver_running = False
    return {"container_running": running, "driver_running": driver_running}


@app.post("/api/ur/start")
def ur_start():
    if docker_client is None:
        raise HTTPException(503, "docker not available")
    try:
        c = docker_client.containers.get(_ur_container_name())
        if c.status != "running":
            raise HTTPException(400, "container mir_ur_driver not running")
    except docker.errors.NotFound:
        raise HTTPException(404, "container mir_ur_driver not found")

    # Lanzar en background dentro del contenedor
    try:
        c.exec_run("nohup bash /ur_start.sh > /var/log/mir/ur_start.log 2>&1 &", detach=True)
    except Exception as e:
        raise HTTPException(500, f"failed to launch ur_start: {e}")
    return {"status": "ok", "action": "starting", "message": "UR driver launching in background"}


@app.post("/api/ur/stop")
def ur_stop():
    if docker_client is None:
        raise HTTPException(503, "docker not available")
    try:
        c = docker_client.containers.get(_ur_container_name())
        if c.status != "running":
            raise HTTPException(400, "container mir_ur_driver not running")
    except docker.errors.NotFound:
        raise HTTPException(404, "container mir_ur_driver not found")

    ok, out = _exec_in_ur_driver("/ur_stop.sh", timeout=10)
    if not ok:
        raise HTTPException(500, f"ur_stop failed: {out}")
    return {"status": "ok", "action": "stopping", "message": out}


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

    cmd = (
        "bash -c 'source /opt/ros/humble/setup.bash && "
        "source /root/workspace/ros_ws/install/setup.bash 2>/dev/null && "
        f"python3 /joint_mover.py {arm} {joint} {delta}'"
    )
    try:
        r = c.exec_run(cmd, stdout=True, stderr=True, demux=False)
        out = (r.output or b"").decode("utf-8", "replace") if isinstance(r.output, bytes) else str(r.output or "")
    except Exception as e:
        raise HTTPException(500, f"exec failed: {e}")

    # Si falló, intentar recovery: resend robot program + reactivar controller
    if r.exit_code != 0 and "goal rejected" in out.lower():
        _sp.run([
            "docker", "exec", c.name,
            "bash", "-c",
            "source /opt/ros/humble/setup.bash && "
            f"ros2 service call /{arm}_io_and_status_controller/resend_robot_program std_srvs/srv/Trigger '{{}}' >/dev/null 2>&1 && "
            f"sleep 1 && "
            f"ros2 control switch_controllers --activate {arm}_joint_trajectory_controller >/dev/null 2>&1"
        ], timeout=10)
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
    raw = await req.body()
    # Sanitizar: JSON no acepta "+0.1", lo convertimos a "0.1"
    sanitized = re.sub(r':\s*\+', ': ', raw.decode("utf-8"))
    body = json.loads(sanitized)
    arm = body.get("arm", "")
    joint = body.get("joint", "")
    delta = body.get("delta", 0.0)
    if arm not in ("left", "right"):
        raise HTTPException(400, "arm must be 'left' or 'right'")
    if joint not in ("shoulder_pan", "shoulder_lift", "elbow", "wrist_1", "wrist_2", "wrist_3"):
        raise HTTPException(400, f"invalid joint: {joint}")
    if abs(delta) > 1.0:
        raise HTTPException(400, "delta too large (max 1.0 rad)")
    if docker_client is None:
        raise HTTPException(503, "docker not available")

    # The move shells into the container and waits for the trajectory result
    # (seconds). Off-load to a thread so concurrent requests — notably the joints
    # polling — keep being served while the arm moves.
    return await asyncio.to_thread(_run_move, arm, joint, delta)


@app.get("/health")
def health():
    return {"status": "ok", "service": "MIR_Suite"}


# Cache de joints para no saturar al contenedor
_ur_joints_cache = {"data": None, "ts": 0.0}
_UR_JOINTS_TTL = 0.1  # 100ms = 10Hz en la UI
JOINT_SERVER_URL = "http://localhost:9091/joints"


@app.get("/api/ur/joints")
async def ur_joints():
    global _ur_joints_cache
    now = asyncio.get_event_loop().time()
    if _ur_joints_cache["data"] is not None and (now - _ur_joints_cache["ts"]) < _UR_JOINTS_TTL:
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


_mir_cache = {"data": None, "ts": 0.0}
_MIR_CACHE_TTL = 60.0


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
        if _mir_cache["data"] is not None and age < _MIR_CACHE_TTL:
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


# Serve index.html at root
@app.get("/")
async def root():
    return FileResponse("static/index.html")


# Mount static files at /static (JS, CSS, 3D models)
app.mount("/static", StaticFiles(directory="static"), name="static")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)