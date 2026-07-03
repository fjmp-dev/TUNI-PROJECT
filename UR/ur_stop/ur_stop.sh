#!/bin/bash
# Stops the UR driver inside the mir_ur_driver container.
# Called from the FastAPI backend via docker exec.
set -e

LOG=/var/log/mir/ur_driver.log
mkdir -p $(dirname $LOG)

echo "[ur_stop] $(date -Iseconds) stopping duo_ur_real..." | tee -a $LOG

# Kill the launch process (this should also kill the children)
PIDS=$(pgrep -f "ros2 launch duo_ur" || true)
if [ -n "$PIDS" ]; then
    echo "[ur_stop] killing PIDs: $PIDS"
    kill $PIDS 2>/dev/null || true
    sleep 2
    # Force if some remain
    PIDS2=$(pgrep -f "ros2 launch duo_ur" || true)
    if [ -n "$PIDS2" ]; then
        echo "[ur_stop] forcing kill -9: $PIDS2"
        kill -9 $PIDS2 2>/dev/null || true
    fi
else
    echo "[ur_stop] no duo_ur running"
fi

# Also kill any UR driver child nodes that may have been left behind
for pat in "ur_ros2_control_node" "urscript_interface" "controller_stopper_node" "robot_state_publisher" "move_group" "force_torque_sensor_broadcaster"; do
    PIDS=$(pgrep -f "$pat" || true)
    [ -n "$PIDS" ] && kill $PIDS 2>/dev/null || true
done

rm -f /tmp/ur_driver.pid
echo "[ur_stop] $(date -Iseconds) stopped" | tee -a $LOG
