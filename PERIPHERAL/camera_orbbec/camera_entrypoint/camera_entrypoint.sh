#!/bin/bash
set -e
source /opt/ros/humble/setup.bash
source /root/workspace/ros_ws/install/setup.bash 2>/dev/null || true

echo "[camera] Starting Orbbec Gemini 330..."
# 640x400 (was 1280x800): the web feed goes through rosbridge as base64 JPEG, and
# 1280x800 frames (~0.29 MB each) saturate it to ~2 FPS. Quartering the pixels
# (~4x smaller frames) lets many more frames through -> a much smoother feed.
exec ros2 launch orbbec_camera gemini_330_series.launch.py \
    color_width:=480 color_height:=270 color_fps:=30 \
    time_domain:=device enable_depth:=false