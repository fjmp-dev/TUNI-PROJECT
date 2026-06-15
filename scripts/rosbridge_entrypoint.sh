#!/bin/bash
set -e

source /opt/ros/humble/setup.bash

echo "[rosbridge] Starting rosbridge_websocket on port 9090..."
exec ros2 launch rosbridge_server rosbridge_websocket_launch.xml port:=9090
