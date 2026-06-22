#!/bin/bash
# Detiene el UR driver dentro del contenedor mir_ur_driver.
# Llamado desde el backend FastAPI via docker exec.
set -e

LOG=/var/log/mir/ur_driver.log
mkdir -p $(dirname $LOG)

echo "[ur_stop] $(date -Iseconds) deteniendo duo_ur_real..." | tee -a $LOG

# Matar el proceso del launch (esto debería matar también a los hijos)
PIDS=$(pgrep -f "ros2 launch duo_ur" || true)
if [ -n "$PIDS" ]; then
    echo "[ur_stop] matando PIDs: $PIDS"
    kill $PIDS 2>/dev/null || true
    sleep 2
    # Forzar si aún quedan
    PIDS2=$(pgrep -f "ros2 launch duo_ur" || true)
    if [ -n "$PIDS2" ]; then
        echo "[ur_stop] forzando kill -9: $PIDS2"
        kill -9 $PIDS2 2>/dev/null || true
    fi
else
    echo "[ur_stop] no hay duo_ur corriendo"
fi

# Matar también los nodos hijos del UR driver que puedan haber quedado
for pat in "ur_ros2_control_node" "urscript_interface" "controller_stopper_node" "robot_state_publisher" "move_group" "force_torque_sensor_broadcaster"; do
    PIDS=$(pgrep -f "$pat" || true)
    [ -n "$PIDS" ] && kill $PIDS 2>/dev/null || true
done

rm -f /tmp/ur_driver.pid
echo "[ur_stop] $(date -Iseconds) detenido" | tee -a $LOG
