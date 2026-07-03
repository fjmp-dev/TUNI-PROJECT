#!/bin/bash
# Launcher for the UR driver (duo_ur_real) inside the mir_ur_driver container.
# Designed to be called from the FastAPI backend via docker exec.
#
# Meant NOT to run automatically when the container starts.
# The user launches it manually from the UI when they want to work with the arms.
set -e

LOG=/var/log/mir/ur_driver.log
mkdir -p $(dirname $LOG)

# If a duo_ur is already running, do nothing
if pgrep -f "ros2 launch duo_ur" >/dev/null; then
    echo "[ur_start] a duo_ur is already running (PIDs: $(pgrep -f 'ros2 launch duo_ur' | tr '\n' ' '))"
    exit 0
fi

source /opt/ros/humble/setup.bash
source /root/workspace/ros_ws/install/setup.bash

echo "[ur_start] $(date -Iseconds) launching duo_ur_real..." | tee -a $LOG

# Launch the driver in the background with output to the log.
# CRITICAL: launch_dashboard_client:=true so the dashboard_client_node come up
# (without them there are no services for recovery/protective stop release/clear errors)
nohup ros2 launch duo_ur duo_ur_real.launch.py \
    launch_rviz:=false \
    headless_mode:=true \
    launch_dashboard_client:=true \
    controller_spawner_timeout:=60 \
    >> $LOG 2>&1 &

UR_PID=$!
disown $UR_PID 2>/dev/null || true
echo $UR_PID > /tmp/ur_driver.pid
echo "[ur_start] duo_ur_real launched (PID $UR_PID), log: $LOG"

# Wait for /move_group to be ready and force use_sim_time:=false
echo "[ur_start] waiting for /move_group..."
for i in $(seq 1 90); do
    if ros2 node info /move_group >/dev/null 2>&1; then
        ros2 param set /move_group use_sim_time false >/dev/null 2>&1 && \
            echo "[ur_start] /move_group use_sim_time=false" | tee -a $LOG
        break
    fi
    sleep 1
done

# Wait (with timeout) for BOTH arms to confirm the RTDE connection: the UR hardware
# component (left_ur/right_ur) goes to 'active' when the driver connects over RTDE.
# list_hardware_components is a service (returns the state instantly), more reliable
# than a blind sleep or echoing the robot_mode topic (latched QoS).
# Returns as soon as they connect; if they don't confirm in time, it warns but continues.
# Configurable with UR_ARMS_TIMEOUT (seconds).
ARMS_TIMEOUT=${UR_ARMS_TIMEOUT:-45}
echo "[ur_start] waiting for RTDE of both arms (left_ur/right_ur active, up to ${ARMS_TIMEOUT}s)..." | tee -a $LOG
arms_deadline=$((SECONDS + ARMS_TIMEOUT))
arms_ok=0
while [ $SECONDS -lt $arms_deadline ]; do
    both=$(ros2 control list_hardware_components 2>/dev/null | sed 's/\x1b\[[0-9;]*m//g' | awk '
        /name: (left_ur|right_ur)/ { cur=$2 }
        /state:/ && cur { if ($0 ~ /label=active/) a[cur]=1; cur="" }
        END { print (("left_ur" in a) && ("right_ur" in a)) ? "yes" : "no" }')
    if [ "$both" = "yes" ]; then
        echo "[ur_start] both arms connected (left_ur/right_ur active)" | tee -a $LOG
        arms_ok=1; break
    fi
    sleep 2
done
[ "$arms_ok" = "1" ] || echo "[ur_start] WARN: arms not confirmed active after ${ARMS_TIMEOUT}s; continuing anyway" | tee -a $LOG

# Try to activate the trajectory controllers
echo "[ur_start] activating trajectory controllers..." | tee -a $LOG
timeout 30 ros2 control switch_controllers \
    --deactivate left_cartesian_motion_controller right_cartesian_motion_controller \
    --activate left_joint_trajectory_controller right_joint_trajectory_controller \
    >> $LOG 2>&1 || echo "[ur_start] WARN: controller switch failed" | tee -a $LOG

# Resend the external control program to the arms (critical to move them)
echo "[ur_start] resending external control program..." | tee -a $LOG
for side in left right; do
    ros2 service call /${side}_io_and_status_controller/resend_robot_program std_srvs/srv/Trigger '{}' >> $LOG 2>&1 && \
        echo "[ur_start]   $side: OK" | tee -a $LOG || \
        echo "[ur_start]   $side: FAIL (may be normal if already running)" | tee -a $LOG
    sleep 2
done

# REACTIVATE the joint_trajectory_controllers (the controller_stopper leaves them inactive)
echo "[ur_start] reactivating joint_trajectory_controllers..." | tee -a $LOG
for i in 1 2 3; do
    timeout 10 ros2 control switch_controllers \
        --activate left_joint_trajectory_controller right_joint_trajectory_controller \
        >> $LOG 2>&1 && break
    echo "[ur_start]   retry $i..." | tee -a $LOG
    sleep 3
done

echo "[ur_start] $(date -Iseconds) ready" | tee -a $LOG
