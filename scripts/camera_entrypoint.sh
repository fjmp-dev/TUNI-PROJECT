#!/bin/bash
set -e
source /opt/ros/humble/setup.bash
source /root/workspace/ros_ws/install/setup.bash 2>/dev/null || true

echo "[camera] Starting Orbbec Gemini 330..."
exec ros2 launch orbbec_camera gemini_330_series.launch.py \
    color_width:=1280 color_height:=800 color_fps:=30 \
    time_domain:=device enable_depth:=false