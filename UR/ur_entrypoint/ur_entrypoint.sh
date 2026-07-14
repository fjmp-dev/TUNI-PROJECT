#!/bin/bash
# Entrypoint of the mir_ur_driver container.
# It NO LONGER launches the UR driver automatically — the user does that from the UI
# (endpoints /api/ur/start and /api/ur/stop).
# This prevents the driver from trying to connect to powered-off or errored arms,
# and lets the user control when it starts.
set -e
source /opt/ros/humble/setup.bash
source /root/workspace/ros_ws/install/setup.bash

mkdir -p /var/log/mir

echo "[ur_driver] container ready, UR driver does NOT start automatically"
echo "[ur_driver] the user must call /api/ur/start from the UI to launch duo_ur_real"

# ---------------------------------------------------------------------------
# supervise <name> <logfile> <command...>
#
# Runs a background service and RESTARTS it if it ever exits. These three
# services (rosbridge, action_bridge, joint_server) used to be launched once with
# `cmd &`: if one died, it stayed dead until someone restarted the whole
# container, while the UI kept showing "offline" with no way back. rosbridge in
# particular is the browser's only live-data path.
#
# Backoff: 2s, doubling to 30s, reset to 2s once a run lasts >60s (so a service
# that crashes instantly does not spin the CPU, but a one-off crash recovers fast).
# ---------------------------------------------------------------------------
supervise() {
    local name="$1" log="$2"; shift 2
    (
        local delay=2
        while true; do
            local start; start=$(date +%s)
            echo "[supervisor] starting $name" >> "$log"
            "$@" >> "$log" 2>&1 || true
            local ran=$(( $(date +%s) - start ))
            [ "$ran" -gt 60 ] && delay=2      # it was healthy for a while -> fast retry
            echo "[supervisor] $name exited after ${ran}s; restarting in ${delay}s" >> "$log"
            sleep "$delay"
            delay=$(( delay * 2 )); [ "$delay" -gt 30 ] && delay=30
        done
    ) &
}

# Always start rosbridge (it is lightweight and useful for diagnostics)
echo "[ur_driver] launching rosbridge on :9090 (locked to read-only whitelist)..."
# SECURITY: the browser only SUBSCRIBES via rosbridge (camera); arm commands
# go through the REST API (docker exec), never through rosbridge. So we deny all
# services + actions and expose only the 3 subscribed topics. This stops anyone on
# the LAN from commanding the arms over :9090 — which would otherwise bypass the UI
# login AND the can_control gate. "[]" = empty whitelist = deny all; actions_glob is
# wired in by the patched launch overlay (UR/rosbridge_hardening/).
ROSBRIDGE_TOPICS="['/camera/color/image_raw/compressed']"
# Behind the Caddy TLS proxy, bind rosbridge to loopback (ROSBRIDGE_ADDRESS=127.0.0.1)
# so :9090 is not reachable from the LAN — Caddy proxies /rosbridge to it. Unset =
# all interfaces (dev / no proxy).
ADDR_ARG=""
[ -n "${ROSBRIDGE_ADDRESS:-}" ] && ADDR_ARG="address:=${ROSBRIDGE_ADDRESS}"
# The literal double-quotes around each value are REQUIRED: without them ros2
# launch parses "[...]" as a STRING_ARRAY, but the node declares these globs as
# STRING and crashes (InvalidParameterTypeException). Quoting forces string type.
supervise rosbridge /var/log/mir/rosbridge.log \
    ros2 launch rosbridge_server rosbridge_websocket_launch.xml \
    port:=9090 $ADDR_ARG \
    "topics_glob:=\"$ROSBRIDGE_TOPICS\"" \
    "services_glob:=\"[]\"" \
    "actions_glob:=\"[]\"" \
    "params_glob:=\"[]\""

# Start action_bridge (also lightweight)
echo "[ur_driver] launching action_bridge (supervised)..."
supervise action_bridge /var/log/mir/action_bridge.log python3 /action_bridge.py

# Start joint_server (HTTP server on :9091 for the UI)
echo "[ur_driver] launching joint_server on :9091 (supervised)..."
supervise joint_server /var/log/mir/joint_server.log python3 /joint_server.py

# Keep the container alive
echo "[ur_driver] waiting for signals..."
trap "echo '[ur_driver] stopped'; kill 0; exit 0" SIGTERM SIGINT
wait
