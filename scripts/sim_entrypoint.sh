#!/bin/bash
set -e
source /opt/ros/humble/setup.bash
source /root/workspace/ros_ws/install/setup.bash

echo "[sim] Patching launch file for fake_hardware..."
# Fix the bug: controllers_active.remove("tcp_pose_broadcaster") should be left/right
LAUNCH_FILE="/root/workspace/ros_ws/src/dev_repos/duo_ur/launch/duo_ur_real.launch.py"
if grep -q 'controllers_active.remove("tcp_pose_broadcaster")' "$LAUNCH_FILE"; then
    sed -i 's/controllers_active.remove("tcp_pose_broadcaster")/controllers_active.remove("left_tcp_pose_broadcaster")\n        controllers_active.remove("right_tcp_pose_broadcaster")/' "$LAUNCH_FILE"
    echo "[sim] Launch file patched"
else
    echo "[sim] Launch file already patched or bug not present"
fi

echo "[sim] Launching duo_ur in FAKE HARDWARE mode..."
ros2 launch duo_ur duo_ur_real.launch.py \
    use_fake_hardware:=true \
    launch_rviz:=false \
    headless_mode:=true \
    controller_spawner_timeout:=60 &
UR_LAUNCH_PID=$!

echo "[sim] Waiting for move_group..."
for i in $(seq 1 60); do
    if ros2 node info /move_group >/dev/null 2>&1; then
        ros2 param set /move_group use_sim_time false >/dev/null 2>&1 && \
            echo "[sim] /move_group use_sim_time set to false" && break
    fi
    sleep 1
done

echo "[sim] Launching rosbridge on port 9090..."
ros2 launch rosbridge_server rosbridge_websocket_launch.xml port:=9090 &
ROSBRIDGE_PID=$!

echo "[sim] Launching action bridge..."
python3 /action_bridge.py &
BRIDGE_PID=$!

echo "[sim] Simulation ready!"
wait
