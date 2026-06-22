#!/bin/bash
source /opt/ros/humble/setup.bash
source /root/workspace/ros_ws/install/setup.bash 2>/dev/null || true

echo "[mir] Starting MiR200 ROS1->ROS2 bridge..."

# Watchdog en background: mata el bridge si está "vivo pero sin datos"
( while true; do
    sleep 30
    bash /mir_watchdog.sh || true
done ) &
WATCHDOG_PID=$!
trap "kill $WATCHDOG_PID 2>/dev/null" EXIT

while true; do
    echo "[mir] Attempting to connect to MiR200 at 192.168.1.13:9090..."
    touch /tmp/mir_bridge_last_io
    python3 -u /mir_raw.py 2>&1 | while IFS= read -r line; do
        echo "$line"
        # Actualizar timestamp de actividad (excepto líneas de descubrimiento que son lentas)
        case "$line" in
            *"[rosbridge_explorer]:"*) ;;
            *) touch /tmp/mir_bridge_last_io ;;
        esac
    done
    echo "[mir] Bridge exited. Retrying in 10s..."
    sleep 10
done

