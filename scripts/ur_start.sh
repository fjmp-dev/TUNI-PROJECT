#!/bin/bash
# Lanzador del UR driver (duo_ur_real) dentro del contenedor mir_ur_driver.
# Diseñado para ser llamado desde el backend FastAPI via docker exec.
#
# Pensado para NO ejecutarse automáticamente al arrancar el contenedor.
# El usuario lo lanza manualmente desde la UI cuando quiere trabajar con los brazos.
set -e

LOG=/var/log/mir/ur_driver.log
mkdir -p $(dirname $LOG)

# Si ya hay un duo_ur corriendo, no hacer nada
if pgrep -f "ros2 launch duo_ur" >/dev/null; then
    echo "[ur_start] ya hay un duo_ur corriendo (PIDs: $(pgrep -f 'ros2 launch duo_ur' | tr '\n' ' '))"
    exit 0
fi

source /opt/ros/humble/setup.bash
source /root/workspace/ros_ws/install/setup.bash

echo "[ur_start] $(date -Iseconds) lanzando duo_ur_real..." | tee -a $LOG

# Lanzar el driver en background con output al log.
# CRÍTICO: launch_dashboard_client:=true para que arranquen los dashboard_client_node
# (sin ellos no hay servicios para recovery/protective stop release/clear errors)
nohup ros2 launch duo_ur duo_ur_real.launch.py \
    launch_rviz:=false \
    headless_mode:=true \
    launch_dashboard_client:=true \
    controller_spawner_timeout:=60 \
    >> $LOG 2>&1 &

UR_PID=$!
disown $UR_PID 2>/dev/null || true
echo $UR_PID > /tmp/ur_driver.pid
echo "[ur_start] duo_ur_real lanzado (PID $UR_PID), log: $LOG"

# Esperar a que /move_group esté listo y forzar use_sim_time:=false
echo "[ur_start] esperando /move_group..."
for i in $(seq 1 90); do
    if ros2 node info /move_group >/dev/null 2>&1; then
        ros2 param set /move_group use_sim_time false >/dev/null 2>&1 && \
            echo "[ur_start] /move_group use_sim_time=false" | tee -a $LOG
        break
    fi
    sleep 1
done

# Esperar 30s a que se conecten los brazos
echo "[ur_start] esperando 30s para brazos..."
sleep 30

# Intentar activar controladores de trayectoria
echo "[ur_start] activando controladores de trayectoria..." | tee -a $LOG
timeout 30 ros2 control switch_controllers \
    --deactivate left_cartesian_motion_controller right_cartesian_motion_controller \
    --activate left_joint_trajectory_controller right_joint_trajectory_controller \
    >> $LOG 2>&1 || echo "[ur_start] WARN: controller switch falló" | tee -a $LOG

# Reenviar el programa de control externo a los brazos (crítico para moverlos)
echo "[ur_start] reenviando programa de control externo..." | tee -a $LOG
for side in left right; do
    ros2 service call /${side}_io_and_status_controller/resend_robot_program std_srvs/srv/Trigger '{}' >> $LOG 2>&1 && \
        echo "[ur_start]   $side: OK" | tee -a $LOG || \
        echo "[ur_start]   $side: FAIL (puede ser normal si ya está corriendo)" | tee -a $LOG
    sleep 2
done

# REACTIVAR los joint_trajectory_controllers (el controller_stopper los deja inactivos)
echo "[ur_start] reactivando joint_trajectory_controllers..." | tee -a $LOG
for i in 1 2 3; do
    timeout 10 ros2 control switch_controllers \
        --activate left_joint_trajectory_controller right_joint_trajectory_controller \
        >> $LOG 2>&1 && break
    echo "[ur_start]   retry $i..." | tee -a $LOG
    sleep 3
done

echo "[ur_start] $(date -Iseconds) listo" | tee -a $LOG
