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
echo "[ur_driver] launching rosbridge on :9090..."
ros2 launch rosbridge_server rosbridge_websocket_launch.xml port:=9090 > /var/log/mir/rosbridge.log 2>&1 &

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
