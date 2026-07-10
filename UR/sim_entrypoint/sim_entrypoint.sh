#!/bin/bash
# Entrypoint for mir_ur_driver_sim.
#
# Boots ONLY the infrastructure (rosbridge + action_bridge + joint_server). The arm
# driver is NOT auto-launched — it starts ON DEMAND (fake hardware) from the UI:
#   /api/nodes/ur_driver/start  ->  ur_start.sh  (with UR_FAKE_HARDWARE=true)
# This matches the real container (driver off until the user wants it).
#
# The duo_ur launch file is provided PATCHED via a read-only overlay mount so Eemil's
# workspace stays pristine; the patch only kicks in when use_fake_hardware:=true.
set -e
source /opt/ros/humble/setup.bash
source /root/workspace/ros_ws/install/setup.bash

mkdir -p /var/log/mir

echo "[sim] Launching rosbridge on :9090 (locked to read-only whitelist)..."
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

echo "[sim] Launching action_bridge..."
python3 /action_bridge.py > /var/log/mir/action_bridge.log 2>&1 &

# joint_server feeds /api/ur/joints; without it the sim cannot serve the joints
# endpoint the real driver exposes.
echo "[sim] Launching joint_server on :9091..."
python3 /joint_server.py > /var/log/mir/joint_server.log 2>&1 &

echo "[sim] Infra ready. Arm driver is OFF — start it on demand from the UI."
trap "echo '[sim] stopped'; kill 0; exit 0" SIGTERM SIGINT
wait
