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
ros2 launch rosbridge_server rosbridge_websocket_launch.xml \
    port:=9090 $ADDR_ARG \
    "topics_glob:=\"$ROSBRIDGE_TOPICS\"" \
    "services_glob:=\"[]\"" \
    "actions_glob:=\"[]\"" \
    "params_glob:=\"[]\"" \
    > /var/log/mir/rosbridge.log 2>&1 &

# Start action_bridge (also lightweight)
echo "[ur_driver] launching action_bridge..."
python3 /action_bridge.py > /var/log/mir/action_bridge.log 2>&1 &

# Start joint_server (HTTP server on :9091 for the UI)
echo "[ur_driver] launching joint_server on :9091..."
python3 /joint_server.py > /var/log/mir/joint_server.log 2>&1 &

# Keep the container alive
echo "[ur_driver] waiting for signals..."
trap "echo '[ur_driver] stopped'; kill 0; exit 0" SIGTERM SIGINT
wait
