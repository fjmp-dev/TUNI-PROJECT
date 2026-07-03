# MIR Suite — Memory Log

**Última actualización:** 2026-06-23  
**Proyecto:** Control web de MIR + UR5e desde navegador  
**Host:** Kevin (MIC-733 / NVIDIA Jetson AGX Orin)

---

## 1. Misión

Construir una suite modular de contenedores Docker para controlar el robot MIR + dos UR5e desde un navegador, sin instalar ROS en el portátil del usuario.

**Principios:**
- **Modularidad:** Cada componente en su propio contenedor
- **Seguridad:** No tocar proyectos originales (`pbd_system/`, `pandai_ark/`, etc.)
- **Web-first:** Todo accesible via navegador en `http://192.168.1.75:8080`
- **Docker-native:** Todo containerizado, `network_mode: host` (kernel Jetson no soporta bridge)

---

## 2. Arquitectura Actual

```
mir_ui (FastAPI :8080)
  ↓ HTTP/WebSocket
rosbridge (:9090) dentro de mir_ur_driver
  ↓ ROS 2 actions/topics
mir_ur_driver (UR driver + MoveIt + rosbridge + action_bridge)
  ↓ puertos 50001-50014
Brazos UR5e (192.168.1.102, 192.168.1.103)

mir_camera (Orbbec Gemini 335Lg)
  ↓ publica /camera/color/image_raw/compressed
  ↓ DDS via network_mode: host
mir_ur_driver (suscribe y retransmite via rosbridge)
  ↓ WebSocket
UI web
```

### Contenedores

| Contenedor | Imagen | Puerto | Propósito |
|---|---|---|---|
| `mir_ui` | `mir_ui:latest` | 8080 | Servir UI web + API Docker + proxy REST MiR |
| `mir_mir` | `mir-mir:latest` | — | Bridge ROS1↔ROS2 del MiR (roslibpy + rclpy) |
| `mir_ur_driver` | `mir-ur-driver:latest` | 9090, 50001-50014 | UR driver + MoveIt + rosbridge + action_bridge |
| `mir_camera` | `mir-camera:latest` | — | Orbbec Gemini 330 (contenedor separado) |

### Volúmenes clave

- `/home/lab/pbd_system:/root/workspace` → Workspace de Eemil (no se modifica, solo se monta)
- `./scripts:/scripts` → Nuestros scripts (action_bridge.py, entrypoints)
- `./config:/mir/config` → Configuración (right_safe_pose.json)
- `/dev:/dev` → Dispositivos USB (cámara)
- `/var/run/docker.sock` → Control de Docker desde mir_ui

---

## 3. Cámara Orbbec

### Configuración

- **Modelo:** Orbbec Gemini 335Lg
- **Resolución:** 1280x800 @ 30fps (MJPG)
- **Conexión:** USB 3.2
- **Serial:** CP4R84P0001W
- **Firmware:** 1.5.55

### Topics publicados

- `/camera/color/image_raw` → Imagen color (raw)
- `/camera/color/image_raw/compressed` → Imagen color (JPEG, para web UI)
- `/camera/color/camera_info` → Parámetros de calibración
- `/camera/depth/points` → Nube de puntos (depth)

### Dockerfile y entrypoint

**Dockerfile** (`docker/camera/Dockerfile`):
```dockerfile
FROM ros2humble_dev_base:latest
COPY scripts/camera_entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
CMD ["bash", "/entrypoint.sh"]
```

**Entrypoint** (`scripts/camera_entrypoint.sh`):
```bash
#!/bin/bash
set -e
source /opt/ros/humble/setup.bash
source /root/workspace/ros_ws/install/setup.bash 2>/dev/null || true

echo "[camera] Starting Orbbec Gemini 330..."
exec ros2 launch orbbec_camera gemini_330_series.launch.py \
    color_width:=1280 color_height:=800 color_fps:=30 \
    time_domain:=device enable_depth:=false
```

### docker-compose.yml (servicio camera)

```yaml
camera:
  build: ./docker/camera
  image: mir-camera:latest
  container_name: mir_camera
  network_mode: host
  privileged: true
  volumes:
    - /home/lab/pbd_system:/root/workspace
    - ./logs:/var/log/mir
    - /dev:/dev
  environment:
    - ROS_DOMAIN_ID=75
  restart: unless-stopped
```

**Nota:** Sin `profiles`, se inicia siempre con `docker compose up`.

### Learnings sobre la cámara

1. **Contenedor separado funciona:** La cámara puede correr en su propio contenedor y comunicarse con `mir_ur_driver` via DDS gracias a `network_mode: host`.

2. **Privilegios necesarios:** Requiere `privileged: true` y `/dev:/dev` para acceso USB.

3. **Workspace montado:** Necesita `/home/lab/pbd_system:/root/workspace` para acceder al paquete `orbbec_camera`.

4. **DDS cross-container:** Los topics de la cámara son visibles desde `mir_ur_driver` sin problemas. Verificado con `ros2 topic list` y `ros2 topic hz` (30.6 Hz).

5. **UI web:** La imagen se recibe via WebSocket como Base64 JPEG y se renderiza en un `<img>` tag.

6. **No necesita estar en el mismo contenedor que el driver:** Anteriormente tuvimos problemas con rosbridge en contenedor separado, pero la cámara sí funciona separada.

### Problema resuelto: Cámara no se veía en la UI

**Síntoma:** La cámara publicaba correctamente (30 Hz), pero la UI no mostraba la imagen.

**Causa raíz:** Rosbridge estaba en un contenedor separado o dentro de `mir_ui`. Cuando intentaba acceder a los topics de la cámara desde otro contenedor, había problemas de descubrimiento DDS. Rosbridge enviaba los datos de imagen como `uint8[]` (JSON array) en lugar de Base64, por lo que la UI no podía renderizar la imagen.

**Solución:**
- Rosbridge está **dentro de mir_ur_driver** (mismo contenedor que el driver de los brazos)
- La cámara está en su propio contenedor (`mir_camera`)
- Ambos usan `network_mode: host`, así que comparten la red del host y DDS funciona correctamente
- Rosbridge puede ver los topics de la cámara y los convierte correctamente a Base64 para la UI

**Por qué funciona ahora:**
1. Rosbridge y la cámara están en la misma red (host)
2. DDS descubre los topics correctamente
3. Rosbridge convierte `sensor_msgs/CompressedImage` a Base64 correctamente
4. La UI se suscribe vía WebSocket y recibe las imágenes

**Lección clave:** El problema no era la cámara, sino rosbridge. La cámara puede estar en contenedor separado, pero rosbridge debe estar en el mismo contenedor que los topics que necesita exponer vía WebSocket.

---

## 3.4 Watchdog del bridge MiR

### Problema

El bridge `mir_raw.py` de Eemil **no maneja la desconexión**: cuando el MiR rosbridge se cuelga (problema conocido, pasa con frecuencia), el bridge queda "vivo pero sin datos" — el proceso Python sigue ejecutando `rclpy.spin()` pero nunca recibe más mensajes. El entrypoint tiene un `while true` que solo reinicia si el proceso muere, pero el bridge nunca muere solo.

**Síntoma:** la UI dice "Sin conexión" y el log del bridge está congelado en el último mensaje.

### Solución

`scripts/mir_watchdog.sh` + entrada modificada en `mir_entrypoint.sh`:

1. El entrypoint lanza un watchdog en background que corre cada 30s
2. El watchdog lee `/tmp/mir_bridge_last_io` (touched por el entrypoint cada vez que el bridge escribe algo a stdout, **excepto** las líneas de topic discovery que son lentas)
3. Si el archivo tiene >90s de antigüedad → `kill -9` al bridge
4. El `while true` del entrypoint lo relanza automáticamente

```bash
# mir_entrypoint.sh
( while true; do sleep 30; bash /mir_watchdog.sh; done ) &

while true; do
    touch /tmp/mir_bridge_last_io
    python3 -u /mir_raw.py 2>&1 | while IFS= read -r line; do
        echo "$line"
        case "$line" in
            *"[rosbridge_explorer]:"*) ;;  # topic discovery = lento
            *) touch /tmp/mir_bridge_last_io ;;
        esac
    done
    sleep 10
done
```

**Regla respetada:** NO se modifica `mir_raw.py` (proyecto original de Eemil), solo se mata y se relanza. Cero cambios al código de Eemil.

### Dockerfile actualizado

```dockerfile
COPY scripts/mir_entrypoint.sh /entrypoint.sh
COPY scripts/mir_raw.py /mir_raw.py
COPY scripts/mir_watchdog.sh /mir_watchdog.sh
RUN chmod +x /entrypoint.sh /mir_watchdog.sh
```

---

## 3.5 Módulo MiR en la UI (REST proxy)

### Endpoint backend

**`GET /api/mir/status`** en `mir_ui` (FastAPI + `httpx.AsyncClient`):

```python
MIR_HOST = "192.168.1.13"
MIR_API_BASE = f"http://{MIR_HOST}/api/v2.0.0"
MIR_TIMEOUT = 8.0  # el MiR a veces tarda ~5-7s en responder

@app.get("/api/mir/status")
async def mir_status():
    async with httpx.AsyncClient(timeout=MIR_TIMEOUT) as client:
        r = await client.get(f"{MIR_API_BASE}/status")
        data = r.json()
    # Mapeo: state_text, battery_percentage, position{x,y,orientation}, velocity, errors, etc.
```

### Datos expuestos (funciona en Pause)

- `state` (Pause / Ready / Running / Error)
- `battery_pct` (con barra de color: >40 verde, 20-40 naranja, <20 rojo)
- `battery_time_s` (formateado a h/m)
- `position {x, y, orientation}` (orientación en grados)
- `velocity {linear m/s, angular rad/s}`
- `mode`, `mission`, `errors` (count + color rojo si >0)
- `uptime_s`, `distance_to_target`, `robot_name`, `map_id`

### Datos NO disponibles en Pause (necesita robot activo)

- Topics ROS en tiempo real (`/robot_pose`, `/scan`, `/odom`, etc.) — rosbridge los publica solo cuando el robot está activo
- `mission_queue` (requiere autenticación HTTP del robot)

### UI

`frontend/index.html` agrega el bloque `.mir-module` entre la cámara y el log. Polling cada 4s + botón "Actualizar" manual. Sin websockets: solo `fetch()` cada 4s.

### Container service mapping

`MIR_SERVICES` en `backend/main.py` ahora incluye `mir_mir` (Bridge MiR) para que aparezca en el panel de containers del UI.

---

## 4. Brazos UR5e

### ⚠️ IMPORTANTE: Brazos montados AL REVÉS (22-Jun-2026)

**Los brazos UR5e están montados volteados, viendo hacia la ESPALDA del robot, no hacia el frente.**

- Cuando planees movimientos, considera que el "frente" del UR5e apunta hacia atrás del MiR
- Los valores positivos de ciertos joints pueden corresponder a direcciones inesperadas
- Verificar visualmente antes de movimientos grandes
- Esto NO está reflejado en el URDF (el modelo asume montaje estándar)
- User pidió: NO mover la muñeca, solo el codo en pruebas iniciales

### Estado actual (22-Jun-2026)

| Brazo | IP | Estado | RobotMode | SafetyMode |
|---|---|---|---|---|
| Izquierdo | 192.168.1.102 | Conectado y funcional | 7 (RUNNING) | 1 (NORMAL) |
| Derecho | 192.168.1.103 | Conectado y funcional | 7 (RUNNING) | 1 (NORMAL) |

**Ambos brazos responden a comandos de movimiento via `joint_trajectory_controller`.**

### Arquitectura de control

```
[UR5e] -> /joint_states (400Hz) -> [joint_server.py :9091] -> [Backend :8080/api/ur/joints] -> [UI]

[UI] -> POST /api/ur/move -> [Backend] -> docker exec joint_mover.py -> Action Server
                       (auto-recovery: resend + reactivar si falla)
```

### Servicios y endpoints

| Endpoint | Metodo | Funcion |
|---|---|---|
| `/api/ur/status` | GET | Estado del contenedor y driver UR |
| `/api/ur/start` | POST | Iniciar driver UR (no automatico) |
| `/api/ur/stop` | POST | Detener driver UR |
| `/api/ur/joints` | GET | Posicion de los 12 joints via proxy HTTP |
| `/api/ur/move` | POST | Mover un joint `{arm, joint, delta}` |

### Componentes nuevos (22-Jun-2026)

| Componente | Puerto | Archivo | Funcion |
|---|---|---|---|
| `joint_server.py` | 9091 | `scripts/joint_server.py` | HTTP server persistente, suscripcion a /joint_states |
| `joint_mover.py` | CLI | `scripts/joint_mover.py` | Mueve un joint via action client |
| `ur_start.sh` | CLI | `scripts/ur_start.sh` | Inicia driver UR con resend + reactivacion |

### Problemas resueltos hoy (22-Jun-2026)

1. **Joints no se veian en la UI:** `joint_server.py` - HTTP server en :9091 que se suscribe una vez a /joint_states (QoS VOLATILE). Backend hace proxy con cache 100ms. Frontend polling 200ms. Deploy sin reiniciar: `docker cp` + `docker exec -d`.

2. **`scaled_joint_trajectory_controller` roto:** Acepta goals pero resultado nunca llega (timeout 15s). Solucion: usar `joint_trajectory_controller` estandar.

3. **`joint_mover.py` crasheaba con AttributeError:** `result_future.result()` retorna None cuando hay timeout. Solucion: verificar `if result is None` antes de acceder a `.status`.

4. **Backend error 500 vacio:** `stderr=False` descartaba el traceback. Solucion: `stderr=True`.

5. **Robot no ejecutaba movimientos:** `robot_program_running = False`. Solucion: llamar a `resend_robot_program`. Agregado auto-resend en `ur_start.sh` y auto-recovery en backend si falla.

6. **Brazo derecho goal rejected:** El `right_controller_stopper` desactivaba el controller. Solucion: reactivar con `ros2 control switch_controllers --activate`. Loop de 3 reintentos en `ur_start.sh`.

7. **UI mostraba "5Hz" vs "400Hz" parpadeante:** Dos funciones JS actualizaban el mismo label. Solucion: unificar a `12 joints @ 400Hz`.

### Botones de control (UI)

| Boton | Accion | Delta |
|---|---|---|
| L -0.1 / L +0.1 | Left elbow grande | 0.1 rad (~5.7 deg) |
| L -0.01 / L +0.01 | Left elbow pequeno | 0.01 rad (~0.57 deg) |
| R -0.1 / R +0.1 | Right elbow grande | 0.1 rad (~5.7 deg) |
| R -0.01 / R +0.01 | Right elbow pequeno | 0.01 rad (~0.57 deg) |

### Flujo de START del driver (ur_start.sh)

1. Lanza `duo_ur_real.launch.py` con `headless_mode:=true launch_dashboard_client:=true`
2. Espera `/move_group` y fuerza `use_sim_time:=false`
3. Espera 30s a que los brazos conecten via RTDE
4. Activa `joint_trajectory_controllers`
5. Reenvia `resend_robot_program` a ambos brazos
6. Reactiva controllers (el stopper los desactiva durante el resend, 3 reintentos)
7. Listo

### Posicion de joints al final de sesion (22-Jun-2026 ~13:00)

| Brazo | Joint | Rad | Deg |
|---|---|---|---|
| Left | shoulder_pan | -0.020 | -1.2 |
| Left | shoulder_lift | -0.706 | -40.4 |
| Left | elbow | 1.230 | 70.5 |
| Left | wrist_1 | -3.218 | -184.3 |
| Left | wrist_2 | -1.558 | -89.3 |
| Left | wrist_3 | -3.335 | -191.1 |
| Right | shoulder_pan | 0.350 | 20.1 |
| Right | shoulder_lift | -2.621 | -150.2 |
| Right | elbow | -0.795 | -45.5 |
| Right | wrist_1 | -1.046 | -59.9 |
| Right | wrist_2 | 1.050 | 60.2 |
| Right | wrist_3 | -5.611 | -321.5 |

### Lecciones aprendidas (brazos)

1. PolyScopeX (nuestro robot) NO tiene dashboard server - solo CB3 y e-Series. Para recovery usar `resend_robot_program`.
2. `rosbridge` WebSocket desde navegador es fragil para /joint_states. HTTP persistente mas confiable.
3. No usar `docker exec` por peticion para datos en tiempo real. Servidor HTTP persistente es 10x mas rapido.
4. QoS VOLATILE vs TRANSIENT_LOCAL: para suscripciones persistentes, VOLATILE basta.
5. `controller_stopper` del UR driver desactiva controllers inesperadamente.
6. Bug en launch de Eemil: `launch_dashboard_client` default `false` en `duo_ur_real.launch.py`.

### action_bridge.py

Recibe JSON por `/mir/command` y traduce a actions de ROS 2:

- `move_arm` → `/move_action` (right) o `/move_to_pose_in_frame` (left)
- `home` → `/move_action` con goal en joint-space a la pose segura
- `stop_arm` → Publica evento (no cancela goals aún)
- `close_hand` / `open_hand` → `/left_humanoid_hand/close_hand` / `open_hand`

**Fix aplicado:** Para el brazo derecho, ahora obtiene la orientación actual del TCP via TF y la mantiene en el goal. Antes forzaba `Quaternion(0,0,0,1)`, lo que torcía la muñeca.

### Posición segura (brazo derecho)

Guardada en `config/right_safe_pose.json`:

```json
{
  "right_shoulder_pan_joint": 0.260066,
  "right_shoulder_lift_joint": -2.511969,
  "right_elbow_joint": -1.541838,
  "right_wrist_1_joint": -0.292104,
  "right_wrist_2_joint": 1.095833,
  "right_wrist_3_joint": -6.021772
}
```

TCP en `table_corner`: `[0.052, 0.920, 0.397]`

---

## 5. Decisiones Técnicas Clave

### network_mode: host

**Problema:** El kernel del Jetson AGX Orin no incluye la tabla `iptables raw`, necesaria para redes bridge de Docker.

**Solución:** Todos los contenedores usan `network_mode: host`. Comparten el namespace de red del host, por lo que `localhost:9090` funciona transparentemente.

### Rosbridge dentro de mir_ur_driver

**Problema:** Cuando rosbridge estaba en contenedor separado, había problemas de descubrimiento DDS con topics stale.

**Solución:** Rosbridge corre dentro de `mir_ur_driver`. La UI se conecta a `ws://192.168.1.75:9090`.

### Cámara en contenedor separado

**Problema:** Anteriormente la cámara corría dentro de `mir_ur_driver` para evitar problemas DDS.

**Solución:** Verificamos que la cámara funciona correctamente en contenedor separado (`mir_camera`). Los topics son visibles via DDS gracias a `network_mode: host`.

### Workspace de Eemil montado, no copiado

**Problema:** No podemos modificar `/home/lab/pbd_system` (regla de aislamiento).

**Solución:** Lo montamos como volumen `/root/workspace` en los contenedores. Usamos sus paquetes (`duo_ur`, `moveit_utils_pkg`, etc.) sin copiarlos.

### use_sim_time fix

**Problema:** `duo_ur_real.launch.py` hardcodea `use_sim_time:=true` para move_group, lo cual rompe MoveIt en hardware real.

**Solución:** El entrypoint espera a que `/move_group` exista y fuerza `use_sim_time:=false` con `ros2 param set`.

---

## 6. Próximos Pasos

### Sesión 22-Jun-2026 - Documentación del problema MiR

**Hechos importantes documentados en `docs/mir_connectivity_issue.md`:**
- MiR200 tiene 2 errores físicos: 10713 (encoder rueda) + 9000 (SICK Safety PLC + Emergency Stop)
- Red del robot colapsa al entrar en Play, vuelve a responder al re-pausar
- Bridge `mir_mir` con watchdog arreglado (90s sin actividad → kill + relaunch)
- Módulo MiR UI funciona con datos via REST API en Pause + cache 60s
- `AVANCE_JUNTA.md` actualizado con 3 preguntas urgentes para el asesor

**PENDIENTE al final de esta sesión:**
- Crear HTML visual (`mir_suite/mir_diagnostic_report.html`) con todo lo encontrado
  - Timeline de eventos
  - Gráficos de Hz
  - Lista de errores con códigos
  - Soluciones intentadas
  - Recomendaciones

**Sesión 22-Jun-2026 (continuación) - Brazos UR5e y joints en UI:**

**Hechos importantes:**
- Brazos UR5e encendidos: `192.168.1.102` (left) y `192.168.1.103` (right) responden ping y puertos
- Driver UR arranca con `launch_dashboard_client:=true` (sin él, los servicios de dashboard no aparecen)
- **Los robots son PolyScopeX** (no e-Series), por eso el `dashboard_client` se sale con warning "dashboard server is only available for CB3 and e-Series"
- UR driver SÍ conecta: hardware components `left_ur` y `right_ur` están `active`, /joint_states publica a 387-450Hz
- Estado del robot (vía `/left_io_and_status_controller/robot_mode`): `mode=7=RUNNING`, `safety_mode=1=NORMAL` (robot NO está en amarillo)
- Bug crítico en `duo_ur_real.launch.py`: `launch_dashboard_client` default es `false` (debería ser `true`)
- UR driver ahora NO se inicia automáticamente con el contenedor — usuario lo lanza desde UI con `Start driver`
- **Documentado en `docs/joints_display_fix.md`:**
  - Solución final: `joint_server.py` (HTTP server en :9091) + proxy backend
  - Bug del Hz parpadeante (5↔400) arreglado: ahora muestra `12 joints @ 400Hz (age X.XXs)`
  - Deploy sin reiniciar: `docker cp` + `docker exec -d` (no mata al driver)

**Lecciones técnicas:**
- PolyScopeX no tiene dashboard server (a diferencia de e-Series)
- `rosbridge` WebSocket desde navegador es frágil para /joint_states (QoS issues)
- `docker exec` por petición es caro (~200ms) vs servidor HTTP persistente (~10ms)
- `transient_local` QoS se necesita solo para clientes que se conectan-desconectan

### Prioridad alta

1. ✅ **Módulo MiR en UI** (completado)
2. ✅ **Watchdog bridge mir_mir** (completado)
3. ✅ **Cache REST API** (completado, 60s TTL)
4. ✅ **Documentación del problema MiR** (completado, `docs/mir_connectivity_issue.md`)
5. ✅ **UR driver con control manual** (completado, UI buttons + /api/ur/start|stop)
6. ✅ **Joint server persistente** (completado, `joint_server.py` en :9091)
7. ✅ **Documentación fix joints** (completado, `docs/joints_display_fix.md`)

8. **Probar un movimiento real**: ahora que /joint_states funciona, enviar un goal al `left_joint_trajectory_controller` o `right_joint_trajectory_controller` para verificar que el robot responde a comandos
9. **Mover brazo manualmente con teach pendant** y ver que UI refleja cambios en tiempo real (validación de lectura)
10. **Hacer un "Home" position** via MoveIt action `move_action`

6. **Módulo Nordbo F/T en UI:** Lanzar `dual_nordbo.launch.py` desde `nordbo_ft_sensor` package, visualizar wrench data en panel.

7. **Módulo de brazos en UI:** Panel de control con Home button, step ±10mm, velocity slider, emergency stop.

### Prioridad media

8. **Simulación segura:** Corregir/crear launch para `use_fake_hardware:=true` (bug en línea ~511 de `duo_ur_real.launch.py`).

9. **Controlador correcto:** Cambiar MoveIt a `right_scaled_joint_trajectory_controller`.

10. **Brazo izquierdo:** Diagnóstico de hardware (teach pendant, URCap, red).

11. **Mano y Nordbo:** Panel de control cuando estén conectados físicamente.

---

## 7. Archivos Clave

```
mir_suite/
├── architecture.html          # Mapeo de arquitectura (HTML visual)
├── docker-compose.yml         # 3 servicios: mir_ui, mir_ur_driver, mir_camera
├── backend/main.py            # FastAPI server
├── frontend/index.html        # UI web (en reconstrucción)
├── scripts/
│   ├── action_bridge.py       # JSON → ROS 2 actions
│   ├── ur_entrypoint.sh       # UR driver + rosbridge + bridge
│   └── camera_entrypoint.sh   # Orbbec camera
├── config/
│   └── right_safe_pose.json   # Pose segura del brazo derecho
├── docker/
│   ├── base/Dockerfile
│   ├── camera/Dockerfile
│   ├── ui/Dockerfile
│   └── ur_driver/Dockerfile
└── models/
    └── ur5e_*.dae             # Meshes para 3D viewer
```

---

## 8. Comandos Útiles

### Iniciar todo

```bash
cd /home/lab/Desktop/MIR/mir_suite
docker compose down
docker compose up -d
```

### Ver logs

```bash
docker logs -f mir_ui
docker logs -f mir_ur_driver
docker logs -f mir_camera
```

### Verificar cámara

```bash
docker exec mir_camera bash -c "source /opt/ros/humble/setup.bash && ros2 topic hz /camera/color/image_raw/compressed"
```

### Verificar brazos

```bash
docker exec mir_ur_driver bash -c "source /opt/ros/humble/setup.bash && source /root/workspace/ros_ws/install/setup.bash && ros2 topic echo /joint_states --once"
```

### Acceder a UI

```
http://192.168.1.75:8080
```

---

## 9. Sesión 2026-06-23 — Banco de pruebas sim + inicio del endurecimiento

Sesión de transición (de opencode a Claude Code). Estrategia acordada con el usuario:
**endurecer la base primero**, luego reescritura grande del frontend, sin deadline.

### Reorganización commiteada

- Movidos los reportes HTML a `reports/` y los docs a `docs/` (renames puros).
- `PROJECT.md` añadido como documento de referencia completo.

### Banco de pruebas sim habilitado (primera tarea del endurecimiento)

Antes el perfil `sim` NO servía como banco de pruebas de los endpoints. Tres bloqueadores
resueltos:

1. **El `sim_entrypoint.sh` modificaba el código de Eemil** vía `sed -i` sobre
   `duo_ur_real.launch.py` (montado read-write). El bug que parchea
   (`controllers_active.remove("tcp_pose_broadcaster")` → debe ser `left_`/`right_`) solo
   corre bajo `use_fake_hardware:=true`.
   **Solución:** vendorizar la versión parcheada en `vendor/duo_ur/duo_ur_real.launch.py` y
   montarla como overlay **read-only solo en el servicio sim**. Eemil restaurado a pristine
   (seguro: el driver real nunca ejecuta ese bloque). Mismo patrón que ya se usa con `mir_raw.py`.
2. **El sim no lanzaba `joint_server`** (:9091) → `/api/ur/joints` no funcionaba. Añadido al
   `sim_entrypoint.sh` y montados `joint_server.py` + `joint_mover.py` en el servicio sim.
3. **El backend apuntaba al contenedor `mir_ur_driver` hardcodeado.** Añadido
   `_ur_container_name()` en `backend/main.py`: auto-detecta el contenedor UR corriendo
   (`mir_ur_driver` real ↔ `mir_ur_driver_sim`), override con env `UR_CONTAINER`. Son
   mutuamente excluyentes (ambos bindean :9090).

**Validado end-to-end contra fake hardware:** `/joint_states` ~490Hz, `left_joint_trajectory_controller`
activo, `/api/ur/move` movió el codo izq 0.0 → 0.05 rad. Stack real restaurado y sano.

### Endurecimiento del backend aplicado (commiteado + subido)

1. **Event loop no se bloquea en `ur_move`.** El `docker exec` del movimiento se manda a un thread con
   `asyncio.to_thread` (`_run_move`). Validado en sim: `/api/ur/joints` respondió en ~5 ms durante un
   movimiento de 15s.
2. **Bug del `pgrep` en `/api/ur/status`** (driver_running siempre `true`): arreglado con el truco del
   corchete `pgrep -f [d]uo_ur_real`. Validado: `false` con driver parado, `true` corriendo.
3. **Validación Pydantic** en `/api/ur/move` (`MoveRequest`): arm/joint `Literal`, delta acotado por
   `UR_MAX_DELTA` (default 0.5). Entradas inválidas → `422`, ya no llegan al brazo.
4. **Config externalizada:** constantes al top como env-overridable; `mir_ui` lee `config/.env` vía
   `env_file`. `_exec_in_ur_driver` ahora respeta su `timeout` (wrapper `timeout`).
5. **`joint_mover.py` fail-safe:** `get_joints()` lanza `RuntimeError` claro si `joint_server` falla;
   `move_joint()` aborta si falta la posición actual en vez de partir de un 0.0 fantasma (evita un salto
   grande inesperado).
6. **Código muerto borrado:** `mirror_node.py` (roto, nunca invocado) y `joint_reader.py` (obsoleto).
7. **`ur_start.sh`:** el `sleep 30` ciego → sondeo real del estado RTDE (componentes hardware
   `left_ur`/`right_ur` `active` vía `ros2 control list_hardware_components`, sin problemas de QoS).
   Sale al conectar, avisa (no aborta) si no confirma en `UR_ARMS_TIMEOUT` (45s). Lógica validada
   contra brazos reales; falta prueba end-to-end con reinicio real del driver.
8. **Watchdog MiR configurable:** `MIR_WATCHDOG_INTERVAL` (30s) y `MIR_WATCHDOG_THRESHOLD` (90s)
   env-overridable; log con timestamp. (No probado en vivo: MiR apagado.)
9. **Recovery del move ampliado:** dispara resend+reactivar también con "controller not available" y
   timeouts, no solo "goal rejected".

**Estado del plan:** Fase 1 (backend) y Fase 2 (scripts) prácticamente cerradas. Pendiente menor:
auth (se cablea con el frontend), routers/logging (opcional), y la prueba end-to-end de `ur_start.sh`.
Siguiente bloque grande: Fase 3 (reescritura del frontend + visor 3D). Ver [[sim-test-bench-setup]].

### Cómo correr el sim (real y sim no coexisten por el puerto 9090)

```bash
docker stop mir_ur_driver && docker restart mir_ui
docker compose --profile sim up -d ur_driver_sim   # ~60-90s
# probar: curl /api/ur/joints ; curl -X POST /api/ur/move ...
# restaurar: docker stop mir_ur_driver_sim && docker rm mir_ur_driver_sim && docker start mir_ur_driver
# (NO usar 'docker compose down' — borraría mir_ui/mir_camera)
```

---

## 10. Sesión 2026-06-25 — Fase 3 (frontend) + primer smart skill

### UI nueva en Svelte (Fase 3) — PUBLICADA

- Reescritura del frontend en **Vite + Svelte 5** (en `web/`), reemplazando el `index.html`
  monolítico. Componentes: Header, CameraPanel (rosbridge), MirPanel, UrPanel, Viewer3D, SkillsPanel,
  LogPanel. Config central (`web/src/lib/`), cliente API con soporte de token (auth futura).
- **Combo estable:** Vite 5 + Svelte 5 (Vite 8 usa rolldown sin binario para aarch64).
- **Publicada en :8080** vía Dockerfile multi-stage (stage node hace `npm run build`, stage python
  sirve `dist/`). `main.py` monta el build en `/` con `html=True` (SPA) tras las rutas `/api/*`.
  Compose ya no monta `./frontend` ni `./models` (van horneados). La `frontend/index.html` vieja
  queda jubilada (en el repo como referencia, no se sirve).
- **UI en inglés** (preferencia del usuario); docs siguen en español.

### Visor 3D — con primitivos (los .dae no renderizan)

- Dibuja ambos brazos con cilindros (eslabones) + esferas (joints) desde `models/ur5e_chain.json`,
  animado en vivo desde `/api/ur/joints`. Izq azul, der naranja.
- Las mallas `.dae` cargan con geometría válida pero NO renderizan en ningún WebGL (bug del archivo);
  la cadena cinemática sí funciona. Diagnosticado con **screenshots de chromium headless**
  (`--use-angle=swiftshader --screenshot`). Fix de eje Z-up→Y-up + auto-encuadre de cámara.

### Smart skills

- **Payload** (primer skill): `POST /api/ur/payload` → servicio `set_payload` (`ur_msgs/SetPayload`).
  Validación Pydantic (masa 0-5kg, CoG acotado). Panel "Smart Skills" en la UI.
- El driver UR ya expone los primitivos para los siguientes: freedrive (`freedrive_mode_controller`),
  force-mode (`start_force_mode`/`stop_force_mode`) — este último para align-to-plane, necesita
  integrar los sensores Nordbo F/T primero.

### Smart skill 2 — Freedrive (probado en hardware, "sirve a la perfección")

- `POST /api/ur/freedrive {arm, enable}`: enable cambia del `joint_trajectory_controller` al
  `freedrive_mode_controller` y lanza un publicador "deadman" a 10Hz en
  `/{arm}_freedrive_mode_controller/enable_freedrive_mode` (se auto-desactiva si para). Disable mata el
  publicador, publica `false`, y restaura el JTC. Corre en thread.
- UI: toggle por brazo en Smart Skills con nota de seguridad (brazo compliant). Store compartido
  `skills.svelte.js` deshabilita los botones de mover de ese brazo mientras está en freedrive.

### Auth (login admin) — prerrequisito del acceso por red

- Middleware exige `X-MIR-Token` en todo `/api/*` excepto `/api/login` y `/health`; estáticos públicos.
  `POST /api/login` valida `AUTH_USER`/`AUTH_PASS` (default admin/admin, en `config/.env`) y devuelve el token.
- UI: pantalla de Login hasta autenticar; token en localStorage; en 401 vuelve al login; botón "Sign out".
- Ver [[auth-and-access-model]].

### Acceso amigable — `tunisuite.local` (puerto 80)

- UI ahora en el **puerto 80** (`UI_PORT` en config/.env) → URL sin `:8080`.
- `tunisuite.local` publicado por **mDNS/Avahi** desde Kevin (`avahi-publish -a -R tunisuite.local
  192.168.1.75`, el `-R` evita el choque del registro inverso con `lab.local`). Persistente con entrada
  `@reboot` en el crontab del usuario. **No requiere tocar la Teltonika.**
- Modelo de acceso: **solo red local** (192.168.1.0/24, ej. WiFi DD-WRT). Probado: desde celular en la
  WiFi del lab → `http://tunisuite.local` → login → movió el codo derecho real. ✅

### Otros

- MiR cache bajado a 20s (config/.env) + banner de "stale" en la UI.
- Documento didáctico `reports/flujo_de_datos.html` (cómo fluyen los datos de cada dispositivo).
- Protocolo de apagado/encendido para cuando Eemil usa los brazos: `docker stop` de nuestros
  contenedores + `ur_stop` para liberar RTDE; revivir con `docker start mir_ui mir_camera mir_ur_driver`.

### Próximo (planeado)

- **Mejorar estabilidad del MiR**: diagnóstico a fondo (REST + interfaz web 192.168.1.13 + físico),
  errores 9000 (safety, probablemente físicos), power-cycle. Necesita MiR en Pause + login de su web + acceso físico.
- Pendiente de definir con Luis: ¿editar controladores ROS desde la suite?
- Nordbo F/T → force-mode/align-to-plane. Botón Home. Telemetría MiR (puente). Terminal (al final).

---

*Documento mantenido por MIR BOT. Última sesión: 2026-06-25.*
