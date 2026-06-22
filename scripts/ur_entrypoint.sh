#!/bin/bash
# Entrypoint del contenedor mir_ur_driver.
# Ya NO lanza el UR driver automáticamente — eso lo hace el usuario desde la UI
# (endpoints /api/ur/start y /api/ur/stop).
# Esto evita que el driver intente conectarse a brazos apagados o en estado
# de error, y permite al usuario controlar cuándo se inicia.
set -e
source /opt/ros/humble/setup.bash
source /root/workspace/ros_ws/install/setup.bash

mkdir -p /var/log/mir

echo "[ur_driver] contenedor listo, UR driver NO se inicia automáticamente"
echo "[ur_driver] el usuario debe llamar /api/ur/start desde la UI para lanzar duo_ur_real"

# Iniciar rosbridge siempre (es ligero y útil para diagnóstico)
echo "[ur_driver] lanzando rosbridge en :9090..."
ros2 launch rosbridge_server rosbridge_websocket_launch.xml port:=9090 > /var/log/mir/rosbridge.log 2>&1 &

# Iniciar action_bridge (también ligero)
echo "[ur_driver] lanzando action_bridge..."
python3 /action_bridge.py > /var/log/mir/action_bridge.log 2>&1 &

# Iniciar joint_server (servidor HTTP en :9091 para la UI)
echo "[ur_driver] lanzando joint_server en :9091..."
python3 /joint_server.py > /var/log/mir/joint_server.log 2>&1 &

# Mantener el contenedor vivo
echo "[ur_driver] esperando señales..."
trap "echo '[ur_driver] detenido'; kill 0; exit 0" SIGTERM SIGINT
wait
