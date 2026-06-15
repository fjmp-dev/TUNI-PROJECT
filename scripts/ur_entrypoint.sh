#!/bin/bash
set -e
source /opt/ros/humble/setup.bash
source /root/workspace/ros_ws/install/setup.bash

echo "[ur_driver] Launching duo_ur_real driver..."
ros2 launch duo_ur duo_ur_real.launch.py \
    launch_rviz:=false \
    headless_mode:=true \
    controller_spawner_timeout:=60 &
UR_LAUNCH_PID=$!

# The duo_ur launch hard-codes use_sim_time:=True for move_group, which is wrong
# for real hardware: it ignores /joint_states because no /clock is published.
echo "[ur_driver] Waiting for /move_group to start, then forcing use_sim_time:=false..."
for i in $(seq 1 60); do
    if ros2 node info /move_group >/dev/null 2>&1; then
        ros2 param set /move_group use_sim_time false >/dev/null 2>&1 && \
            echo "[ur_driver] /move_group use_sim_time set to false" && break
    fi
    sleep 1
done

echo "[ur_driver] Launching rosbridge on port 9090..."
ros2 launch rosbridge_server rosbridge_websocket_launch.xml port:=9090 &
ROSBRIDGE_PID=$!

echo "[ur_driver] Launching action bridge..."
python3 /action_bridge.py &
BRIDGE_PID=$!

echo "[ur_driver] Waiting 60s for arms to connect..."
sleep 60

echo "[ur_driver] Activating trajectory controllers..."
timeout 30 ros2 control switch_controllers \
    --deactivate left_cartesian_motion_controller right_cartesian_motion_controller \
    --activate left_joint_trajectory_controller right_joint_trajectory_controller \
    2>&1 || echo "[ur_driver] WARNING: controller switch timed out (may be OK)"

echo "Started: UR driver PID=$UR_LAUNCH_PID, ROSBridge PID=$ROSBRIDGE_PID, Bridge PID=$BRIDGE_PID"
wait
