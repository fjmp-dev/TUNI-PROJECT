#!/bin/bash
# Entrypoint for mir_ur_driver_sim: launches duo_ur in fake-hardware mode so the
# full endpoint chain (joints + move) can be exercised without real arms.
#
# The duo_ur launch file is provided PATCHED via a read-only overlay mount
# (mir_suite/vendor/duo_ur/duo_ur_real.launch.py). We no longer sed Eemil's code:
# his workspace stays pristine and our only change lives inside mir_suite/.
set -e
source /opt/ros/humble/setup.bash
source /root/workspace/ros_ws/install/setup.bash

mkdir -p /var/log/mir

echo "[sim] Launching duo_ur in FAKE HARDWARE mode..."
ros2 launch duo_ur duo_ur_real.launch.py \
    use_fake_hardware:=true \
    launch_rviz:=false \
    headless_mode:=true \
    controller_spawner_timeout:=60 > /var/log/mir/sim_driver.log 2>&1 &

echo "[sim] Waiting for move_group..."
for i in $(seq 1 60); do
    if ros2 node info /move_group >/dev/null 2>&1; then
        ros2 param set /move_group use_sim_time false >/dev/null 2>&1 && \
            echo "[sim] /move_group use_sim_time set to false" && break
    fi
    sleep 1
done

echo "[sim] Launching rosbridge on :9090..."
ros2 launch rosbridge_server rosbridge_websocket_launch.xml port:=9090 > /var/log/mir/rosbridge.log 2>&1 &

echo "[sim] Launching action_bridge..."
python3 /action_bridge.py > /var/log/mir/action_bridge.log 2>&1 &

# joint_server feeds /api/ur/joints; without it the sim cannot serve the joints
# endpoint the real driver exposes.
echo "[sim] Launching joint_server on :9091..."
python3 /joint_server.py > /var/log/mir/joint_server.log 2>&1 &

echo "[sim] Simulation ready (fake hardware)."
trap "echo '[sim] detenido'; kill 0; exit 0" SIGTERM SIGINT
wait
