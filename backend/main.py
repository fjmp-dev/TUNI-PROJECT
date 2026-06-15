from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn

app = FastAPI(title="MIR Suite")

# ============================================================
# Docker service management (requires /var/run/docker.sock)
# ============================================================
try:
    import docker
    docker_client = docker.from_env()
except Exception:
    docker_client = None

MIR_SERVICES = {
    "mir_ui":       {"label": "Web UI",        "profiles": ["always"]},
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


@app.get("/health")
def health():
    return {"status": "ok", "service": "MIR_Suite"}


# Serve index.html at root
@app.get("/")
async def root():
    return FileResponse("static/index.html")


# Mount static files at /static (JS, CSS, 3D models)
app.mount("/static", StaticFiles(directory="static"), name="static")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)