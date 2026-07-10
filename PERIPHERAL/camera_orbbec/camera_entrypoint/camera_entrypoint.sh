#!/bin/bash
# Camera container. The camera node is NOT auto-launched — it starts ON DEMAND
# from the UI via /api/nodes/camera_color or /api/nodes/camera_depth. Only ONE
# variant can run at a time (single USB device), so they're separate launcher nodes.
source /opt/ros/humble/setup.bash
source /root/workspace/ros_ws/install/setup.bash 2>/dev/null || true
mkdir -p /var/log/mir

echo "[camera] Container up. Camera is OFF — start 'Camera (color)' or 'Camera (color+depth)' from the UI."
trap "echo '[camera] stopped'; kill 0; exit 0" SIGTERM SIGINT
sleep infinity &
wait
