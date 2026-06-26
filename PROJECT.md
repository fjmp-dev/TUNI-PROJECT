# MIR Suite - Documentacion Completa del Proyecto

**Ultima actualizacion:** 25 de junio de 2026
**Ubicacion:** `/home/lab/Desktop/MIR/mir_suite`
**Repositorio:** `github.com/fjmp-dev/TUNI-PROJECT`
**Host:** Kevin (MIC-733 / NVIDIA Jetson AGX Orin)
**Sistema operativo:** Ubuntu 22.04 con ROS 2 Humble

---

## Tabla de Contenidos

1. [Resumen del Proyecto](#1-resumen-del-proyecto)
2. [Hardware y Red](#2-hardware-y-red)
3. [Arquitectura del Sistema](#3-arquitectura-del-sistema)
4. [Contenedores Docker](#4-contenedores-docker)
5. [Backend API](#5-backend-api)
6. [Interfaz Web](#6-interfaz-web)
7. [Integracion MiR200](#7-integracion-mir200)
8. [Integracion Brazos UR5e](#8-integracion-brazos-ur5e)
9. [Decisiones Tecnicas Clave](#9-decisiones-tecnicas-clave)
10. [Bugs Encontrados y Corregidos](#10-bugs-encontrados-y-corregidos)
11. [Inventario de Archivos](#11-inventario-de-archivos)
12. [Comandos de Operacion](#12-comandos-de-operacion)
13. [Proximos Pasos](#13-proximos-pasos)
14. [Preguntas para el Tutor](#14-preguntas-para-el-tutor)
15. [Reglas del Proyecto](#15-reglas-del-proyecto)

---

## 1. Resumen del Proyecto

### Objetivo

Construir una suite modular de contenedores Docker para controlar el robot MiR200 y dos brazos UR5e desde un navegador web, sin necesidad de instalar ROS en la computadora del usuario.

### Principios

- **Modularidad:** Cada componente (camara, driver UR, bridge MiR, UI) en su propio contenedor Docker
- **Seguridad:** No modificar, copiar ni alterar los proyectos originales de Eemil (`pbd_system/`, `pandai_ark/`, `teleop/`, `ur_ws/`, `aiprism_ws/`)
- **Web-first:** Todo accesible via navegador en `http://tunisuite.local` (o `http://192.168.1.75`), con login
- **Docker-native:** Todo containerizado, usando `network_mode: host` porque el kernel del Jetson no soporta redes bridge de Docker
- **Control manual:** Los servicios criticos (driver UR) no se inician automaticamente; el usuario los activa desde la UI

### Acceso

- **URL:** `http://tunisuite.local` (nombre via mDNS/Avahi, publicado por Kevin; tambien `http://192.168.1.75`). Sin el `:8080` — la UI escucha en el **puerto 80** (`UI_PORT`).
- **Login:** un solo usuario admin (`admin`/`admin` por defecto, configurable en `config/.env`: `AUTH_USER`/`AUTH_PASS`/`AUTH_TOKEN`).
- **Red:** acceso solo desde la red local del lab (`192.168.1.0/24`, p. ej. WiFi del DD-WRT o la Teltonika). No expuesto a internet publico (controla robots).

### Estado actual (25-Jun-2026)

| Componente | Estado |
|---|---|
| UI web (Svelte) | Funcionando. Login, camara, MiR, UR5e, visor 3D, smart skills. Servida en :80 desde la imagen |
| Camara Orbbec | Funcionando. 30 FPS, 1280x800 MJPG |
| Brazos UR5e | Ambos funcionales. 12 joints en vivo, control de codos, payload y freedrive desde la UI |
| Visor 3D | Funcionando con primitivos (cilindros+esferas) animados desde /joint_states |
| MiR200 | Inestable. Funciona en Pause via REST API. Errores fisicos (9000) en Play |
| Sensores Nordbo | Responden en red. No integrados en UI aun |

---

## 2. Hardware y Red

### Dispositivos en la red 192.168.1.0/24

| Dispositivo | IP | MAC | Puerto | Estado |
|---|---|---|---|---|
| MiR200 (MiR_S455) | 192.168.1.13 | 34:41:5d:3e:55:f3 | 22, 80, 443, 9090 | Inestable |
| UR5e Izquierdo | 192.168.1.102 | -- | 22, 30001-30004 | Funcional |
| UR5e Derecho | 192.168.1.103 | -- | 22, 30001-30004 | Funcional |
| Nordbo FT #1 | 192.168.1.112 | e4:5f:01:da:93:9a | 2001, 2003 | Online |
| Nordbo FT #2 | 192.168.1.113 | e4:5f:01:da:99:7a | 2001, 2003 | Online |
| Gateway (Teltonika) | 192.168.1.1 | 20:97:27:31:d5:6f | 22, 80, 443 | Online |
| DD-WRT Router | 192.168.1.2 | -- | 80, 23 | Online |
| Dispositivo misterioso | 192.168.1.10 | 00:06:77:4e:9e:6c | -- | Online |

### Interfaces de Kevin (Jetson AGX Orin)

| Interfaz | IP | Proposito |
|---|---|---|
| lan1 | 195.148.48.186 | Internet / Universidad |
| lan2 | 192.168.1.75 | Red de robots |
| lan4 | 192.168.1.75 | Red de robots (duplicada, puede causar ARP flux) |
| docker0 | 172.17.0.1 | Red interna de Docker |

### ROS Configuration

- **ROS_DOMAIN_ID:** 75 (compartido por todos los contenedores)
- **ROS 2 Distro:** Humble
- **Middleware:** rmw_fastrtps_cpp
- **QoS:** Principalmente RELIABLE + VOLATILE. TRANSIENT_LOCAL solo cuando se necesita el ultimo valor al conectar

---

## 3. Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────────┐
│                   Kevin - Jetson AGX Orin                    │
│                     Sistema operativo Ubuntu                 │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   mir_ui     │  │ mir_camera   │  │mir_ur_driver │      │
│  │   :8080      │  │  (USB)       │  │  :9090 :9091 │      │
│  │              │  │              │  │              │      │
│  │ FastAPI +    │  │ Orbbec       │  │ duo_ur_real  │      │
│  │ HTML/JS UI   │  │ Gemini 335Lg │  │ MoveIt       │      │
│  │              │  │              │  │ rosbridge    │      │
│  │ /api/mir/*   │  │ /camera/*    │  │ action_bridge│      │
│  │ /api/ur/*    │  │ 30fps MJPG   │  │ joint_server │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                 │                 │               │
│  ┌──────┴───────┐         │         ┌──────┴───────┐       │
│  │   mir_mir    │         │         │   volumes    │       │
│  │  (pausado)   │         │         │ pbd_system   │       │
│  │              │         │         │ /dev         │       │
│  │ miR bridge   │         │         │ scripts/     │       │
│  │ ROS1→ROS2    │         │         │ config/      │       │
│  └──────────────┘         │         └──────────────┘       │
│                            │                                │
└────────────────────────────┼────────────────────────────────┘
                             │
              ┌──────────────┴──────────────┐
              │     Red 192.168.1.0/24      │
              │     network_mode: host       │
              └──────────────┬──────────────┘
                             │
        ┌──────────┬─────────┼─────────┬──────────┐
        │          │         │         │          │
   ┌────┴───┐ ┌───┴───┐ ┌───┴───┐ ┌───┴───┐ ┌────┴───┐
   │ MiR200 │ │UR5e L │ │UR5e R │ │Nordbo1│ │Nordbo2 │
   │ .13    │ │ .102  │ │ .103  │ │ .112  │ │ .113   │
   └────────┘ └───────┘ └───────┘ └───────┘ └────────┘
```

### Flujo de datos

**Lectura de joints (brazos → pagina):**
```
UR5e → RTDE → ur_ros2_control_node → /joint_states (400Hz)
       → joint_server.py (HTTP :9091)
       → Backend FastAPI /api/ur/joints (proxy + cache 100ms)
       → Frontend polling cada 200ms → UI
```

**Escritura de comandos (pagina → brazos):**
```
UI boton → POST /api/ur/move {arm, joint, delta}
         → Backend docker exec joint_mover.py
         → Action client → joint_trajectory_controller
         → Hardware interface → UR5e se mueve
```

**Datos del MiR (MiR → pagina):**
```
MiR200 → REST API :80/api/v2.0.0/status → Backend proxy /api/mir/status
       → UI polling cada 4s (cache 60s)
MiR200 → rosbridge :9090 → mir_mir container (mir_raw.py)
       → topics ROS2 en Kevin
```

---

## 4. Contenedores Docker

### Resumen

| Contenedor | Imagen | Puerto | Profile | Proposito |
|---|---|---|---|---|
| `mir_ui` | `mir_ui:latest` | 8080 | (siempre) | Web UI + REST API backend |
| `mir_camera` | `mir-camera:latest` | -- | (siempre) | Orbbec Gemini 335Lg |
| `mir_ur_driver` | `mir-ur-driver:latest` | 9090, 9091 | `arms` / `full` | UR5e driver + MoveIt + rosbridge + joint_server |
| `mir_mir` | `mir-mir:latest` | -- | (siempre) | Bridge ROS1→ROS2 del MiR200 |
| `mir_ur_driver_sim` | `mir-ur-driver:latest` | 9090 | `sim` | Driver simulado para pruebas sin hardware |

### mir_ui

**Dockerfile:** `docker/ui/Dockerfile` (**multi-stage**: etapa Node compila la UI Svelte con `npm run build`, etapa Python sirve el `dist/`)
**Base:** `node:20-slim` (build) + `python:3.11-slim` (runtime)
**Dependencias:** fastapi, uvicorn, docker, httpx, pydantic
**Puerto:** 80 (`UI_PORT`)

**Autenticacion:** un middleware exige `X-MIR-Token` en todo `/api/*` excepto `/api/login` y `/health`; los estaticos quedan publicos para que cargue el login.

**Endpoints:**
- `GET /` — sirve la UI Svelte compilada (SPA)
- `GET /health` — health check (publico)
- `POST /api/login` — login admin; devuelve el token (publico)
- `GET /api/containers` — lista de contenedores
- `POST /api/containers/{name}/start|stop` — iniciar/detener contenedor
- `GET /api/mir/status` — proxy REST al MiR200 (cache 20s, flag stale)
- `GET /api/ur/status` — estado del driver UR (pgrep con truco del corchete)
- `POST /api/ur/start` / `POST /api/ur/stop` — iniciar/detener driver UR
- `GET /api/ur/joints` — proxy HTTP al joint_server
- `POST /api/ur/move` — mover un joint (validado con Pydantic, ejecuta en thread)
- `POST /api/ur/payload` — setear payload (servicio set_payload)
- `POST /api/ur/freedrive` — activar/desactivar freedrive por brazo

**Volumenes:**
```yaml
- ./backend/main.py:/app/main.py   # solo main.py; la UI va horneada en la imagen
- /var/run/docker.sock:/var/run/docker.sock
# env_file: ./config/.env  (MIR_IP, UI_PORT, AUTH_*, MIR_CACHE_TTL, ...)
```

### mir_ur_driver

**Dockerfile:** `docker/ur_driver/Dockerfile`
**Base:** `ros2humble_dev_base:latest`
**Entrypoint:** `scripts/ur_entrypoint.sh`

**Que se inicia automaticamente al arrancar el contenedor:**
1. rosbridge_server en :9090
2. action_bridge.py (traduce JSON a acciones ROS)
3. joint_server.py en :9091 (sirve /joint_states a la UI)

**Que NO se inicia automaticamente (el usuario lo lanza desde la UI):**
1. duo_ur_real.launch.py (el driver de los brazos UR5e)

**Scripts disponibles:**
- `ur_start.sh` — lanza el driver UR con todos los pasos de recuperacion
- `ur_stop.sh` — detiene el driver UR limpiamente
- `joint_mover.py` — mueve un joint via action client

**Volumenes clave:**
```yaml
- /home/lab/pbd_system:/root/workspace    # Workspace de Eemil (solo lectura)
- ./scripts/action_bridge.py:/action_bridge.py
- ./scripts/ur_entrypoint.sh:/entrypoint.sh
- ./scripts/joint_server.py:/joint_server.py
- ./scripts/joint_mover.py:/joint_mover.py
- ./scripts/ur_start.sh:/ur_start.sh
- ./scripts/ur_stop.sh:/ur_stop.sh
- /dev:/dev                                # Acceso a dispositivos
```

### mir_mir

**Dockerfile:** `docker/mir/Dockerfile`
**Base:** `ros2humble_dev_base:latest`
**Dependencias pip:** roslibpy
**Entrypoint:** `scripts/mir_entrypoint.sh`

**Funcionamiento:**
1. El entrypoint lanza un watchdog en background (cada 30s verifica actividad)
2. Entra en un loop infinito: lanza `mir_raw.py`, si muere espera 10s y relanza
3. El watchdog mata el proceso si pasan 90s sin actividad en stdout
4. Cero modificaciones al codigo de Eemil — solo matamos y relanzamos

**Scripts montados:**
- `mir_raw.py` — bridge ROS1→ROS2 de Eemil (original, sin modificar)
- `mir_watchdog.sh` — watchdog de auto-recuperacion
- `mir_entrypoint.sh` — entrypoint con loop de reconexion

### mir_camera

**Dockerfile:** `docker/camera/Dockerfile`
**Base:** `ros2humble_dev_base:latest`
**Entrypoint:** `scripts/camera_entrypoint.sh`

**Configuracion:**
- Orbbec Gemini 335Lg
- Resolucion: 1280x800 a 30fps
- Formato: MJPG
- Depth: deshabilitado por ahora
- Conexion: USB 3.2

---

## 5. Backend API

### Endpoints MiR

| Endpoint | Metodo | Descripcion |
|---|---|---|
| `/api/mir/status` | GET | Proxy a `http://192.168.1.13:80/api/v2.0.0/status`. Devuelve JSON con bateria, posicion, velocidad, estado, errores. Cache de 60s. Si falla y hay datos en cache, los devuelve con flag `stale=true`. |

**Respuesta tipica:**
```json
{
  "ok": true,
  "state": "Pause",
  "mode": "Mission",
  "battery_pct": 66.7,
  "battery_time_s": 32904,
  "position": {"x": 12.49, "y": 11.08, "orientation": -2.82},
  "velocity": {"linear": 0.0, "angular": 0.0},
  "errors": [],
  "uptime_s": 1394,
  "robot_name": "MiR_S455"
}
```

### Endpoints UR5e

| Endpoint | Metodo | Descripcion |
|---|---|---|
| `/api/ur/status` | GET | Estado del contenedor y del driver. `{"container_running": bool, "driver_running": bool}` |
| `/api/ur/start` | POST | Inicia el driver UR via `ur_start.sh` en background |
| `/api/ur/stop` | POST | Detiene el driver UR via `ur_stop.sh` |
| `/api/ur/joints` | GET | Proxy a `http://localhost:9091/joints`. Devuelve los 12 joints. Cache 100ms. |
| `/api/ur/move` | POST | Mueve un joint. Body: `{"arm","joint","delta"}` (validado con Pydantic). Corre en thread (no bloquea). Auto-recovery si falla. |
| `/api/ur/payload` | POST | Setea el payload del brazo via servicio `set_payload`. Body: `{"arm","mass","cog_x","cog_y","cog_z"}`. No mueve. |
| `/api/ur/freedrive` | POST | Activa/desactiva freedrive por brazo. Body: `{"arm","enable"}`. Cambia de controller + publicador deadman. |

Todos los `/api/*` (excepto `/api/login`) exigen el header `X-MIR-Token` (auth).

**Respuesta de `/api/ur/joints`:**
```json
{
  "names": ["right_elbow_joint", "left_elbow_joint", ...],
  "position": [-0.845, 1.262, ...],
  "left": {"elbow_joint": 1.262, "shoulder_pan_joint": -0.020, ...},
  "right": {"elbow_joint": -0.845, "shoulder_pan_joint": 0.350, ...},
  "age_s": 0.005,
  "stale": false
}
```

### Auto-recovery en /api/ur/move

Si el movimiento falla con "goal rejected", el backend automaticamente:
1. Llama a `resend_robot_program` para reenviar el script al robot
2. Reactiva el `joint_trajectory_controller` con `ros2 control switch_controllers`
3. Reintenta el movimiento
4. Si funciona, responde con `"recovered": true`

---

## 6. Interfaz Web

### Stack

Reescrita en **Vite + Svelte 5** (carpeta `web/`), reemplazando el `frontend/index.html` monolitico viejo (jubilado, queda como referencia). Texto de la UI en **ingles**. Se compila a estaticos y FastAPI los sirve (no hace falta dev server en produccion). Para iterar: `cd web && npm run dev` levanta un dev server en `:5173` con proxy de `/api` al backend.

### Componentes (`web/src/components/`)

1. **Login:** pantalla de acceso (admin/admin) — se muestra hasta autenticar.
2. **Header:** titulo, indicador de conexion rosbridge, boton "Sign out".
3. **CameraPanel:** video en vivo (JPEG via rosbridge/roslib), FPS, Start/Stop.
4. **MirPanel:** bateria con barra, posicion, velocidad, modo, mision, errores. Polling REST con backoff; banner claro de datos "stale".
5. **UrPanel:** estado del driver, Start/Stop, 12 joints en vivo, control de codos (deshabilitado si el brazo esta en freedrive).
6. **Viewer3D:** brazos UR5e en 3D con **primitivos** (cilindros+esferas) animados desde `/joint_states`. No usa las mallas `.dae` (no renderizan).
7. **SkillsPanel:** **Payload** (masa + CoG) y **Freedrive** (toggle por brazo, con nota de seguridad). Force-mode/align-to-plane pendientes (Nordbo F/T).
8. **LogPanel:** registro de eventos.

### Capa de datos (`web/src/lib/`)

- `config.js` — config central (API base, `ws://…:9090`, topics, intervalos, token).
- `api.js` — cliente REST; manda el `X-MIR-Token`; en 401 vuelve al login.
- `auth.svelte.js` — estado de sesion (token en localStorage).
- `joints.svelte.js` — poller compartido de `/api/ur/joints` (alimenta UrPanel + Viewer3D).
- `ros.svelte.js` — conexion rosbridge (cámara, estado conectado).
- `skills.svelte.js`, `log.svelte.js` — estado compartido (freedrive, log).

### Nota de seguridad (brazos)

Los brazos estan montados **al reves** (hacia la espalda del MiR). Las direcciones + y - pueden corresponder a movimientos contrarios a lo esperado. En pruebas solo se mueve el codo; munecas no se tocan. El visor 3D muestra los joints tal cual (no compensa el montaje).

---

## 7. Integracion MiR200

### Estado del Robot

**Errores activos (22-Jun-2026):**

| Codigo | Modulo | Descripcion | Severidad |
|---|---|---|---|
| 10713 | Motorcontroller | Large encoder delay detected | Media |
| 9000 | Safety System / Communication | SICK Safety PLC is OK | Critica |
| 9000 | Safety System / Emergency Stop | Emergency Stop is OK | Critica |

### Comportamiento de la red

| Estado del MiR | Ping | REST API (:80) | Rosbridge (:9090) | Topics ROS |
|---|---|---|---|---|
| Pause | OK | OK | Intermitente | Sin datos |
| Play / Running | CAE | CAE | CAE | CAE |
| Error | Variable | Variable | CAE | Sin datos |

**Conclusion:** Los errores 9000 (safety PLC + emergency stop) causan que el sistema interno del robot se sobrecargue al activarse, colapsando los servicios de red. Solo es estable en Pause.

### Bridge ROS1→ROS2 (mir_mir)

- Usa `mir_raw.py` de Eemil — **sin modificar**
- Se conecta al rosbridge del MiR en `ws://192.168.1.13:9090`
- Descubre automaticamente los 199 topics ROS1
- Crea publicadores equivalentes en ROS2 (132 mapeados exitosamente)
- El watchdog (`mir_watchdog.sh`) lo reinicia si queda congelado

### Panel MiR en la UI

- Usa la REST API (puerto 80), mas estable que rosbridge
- Funciona en Pause — NO requiere que el robot este en Running
- Datos mostrados: bateria, posicion, velocidad, estado, modo, mision, errores
- Cache de 60s con indicador visual de "datos viejos"
- Polling cada 4s + boton Refresh manual

---

## 8. Integracion Brazos UR5e

### Estado de los Brazos

| Brazo | IP | RobotMode | SafetyMode | Controller Activo |
|---|---|---|---|---|
| Izquierdo | 192.168.1.102 | 7 (RUNNING) | 1 (NORMAL) | left_joint_trajectory_controller |
| Derecho | 192.168.1.103 | 7 (RUNNING) | 1 (NORMAL) | right_joint_trajectory_controller |

### IMPORTANTE: Brazos montados al reves

Los brazos UR5e estan montados sobre el torso del MiR200 viendo hacia la ESPALDA, no hacia el frente. Esto significa:
- El "frente" del UR5e apunta hacia atras del MiR
- Los valores positivos/negativos de los joints pueden corresponder a direcciones inesperadas
- Verificar visualmente antes de movimientos grandes
- El URDF (modelo 3D) NO refleja este montaje
- Solo movemos codos en pruebas; munecas no se tocan

### Flujo de inicio del driver (ur_start.sh)

1. Lanza `duo_ur_real.launch.py` con `headless_mode:=true launch_dashboard_client:=true controller_spawner_timeout:=60`
2. Espera a que `/move_group` este listo
3. Fuerza `use_sim_time:=false` (el launch lo hardcodea a true)
4. Espera 30 segundos a que los brazos conecten via RTDE
5. Activa los `joint_trajectory_controllers`
6. Reenvia `resend_robot_program` a ambos brazos
7. Reactiva los controllers (el controller_stopper los apaga durante el resend, 3 reintentos)

### Servidores y Componentes

| Componente | Puerto | Funcion |
|---|---|---|
| `joint_server.py` | 9091 | Servidor HTTP persistente. Se suscribe a /joint_states. Sirve la ultima posicion como JSON. |
| `joint_mover.py` | CLI | Script que recibe `arm joint delta` y envia una trayectoria al action server. |
| `rosbridge` | 9090 | WebSocket para topics ROS. Usado por la camara y otros datos en la UI. |
| `ur_ros2_control_node` | -- | Nodo principal del driver UR. Publica joints a 400Hz. |

### Posicion de referencia de los joints (fin de sesion 22-Jun-2026)

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

---

## 9. Decisiones Tecnicas Clave

### network_mode: host

**Razon:** El kernel del Jetson AGX Orin no incluye `iptables raw`, necesaria para redes bridge de Docker. Todos los contenedores comparten el namespace de red. `localhost:9090` funciona entre contenedores.

### Rosbridge dentro de mir_ur_driver

**Razon:** Cuando rosbridge estaba en contenedor separado, habia problemas de descubrimiento DDS. Al estar en el mismo contenedor que el driver UR, los topics son locales.

### Workspace de Eemil montado como volumen (no copiado)

`/home/lab/pbd_system:/root/workspace` — montamos el workspace de Eemil en modo lectura para usar sus paquetes (`duo_ur`, `moveit_utils_pkg`, `nordbo_ft_sensor`, etc.) sin copiarlos ni modificarlos.

### UR driver NO se inicia automaticamente

El usuario debe presionar "Start driver" en la UI. Esto evita que el driver intente conectarse a brazos apagados o con errores.

### Servidor HTTP persistente (joint_server.py) vs docker exec

Para datos en tiempo real como /joint_states, un servidor HTTP que se suscribe una sola vez es 10x mas rapido que lanzar `docker exec` por cada consulta. Se despliega sin reiniciar el contenedor.

### Joint Trajectory Controller (estandar) vs Scaled Controller

El `scaled_joint_trajectory_controller` esta roto: acepta goals pero nunca los completa (timeout >15s). Usamos el `joint_trajectory_controller` estandar de ROS2.

### PolyScopeX vs e-Series

Nuestros UR5e usan PolyScopeX (software nuevo de Universal Robots). El `dashboard_client` (servicios de recovery) NO funciona en PolyScopeX — solo en e-Series. Para recovery usamos `resend_robot_program`.

### Vendoring del launch de Eemil en vez de modificarlo (23-Jun-2026)

El perfil `sim` necesita un fix en `duo_ur_real.launch.py` (el `controllers_active.remove("tcp_pose_broadcaster")` debe ser `left_`/`right_`, solo bajo `use_fake_hardware:=true`). Antes el `sim_entrypoint.sh` lo aplicaba con `sed -i` sobre el codigo montado de Eemil — violacion de la regla de aislamiento. Ahora la version parcheada vive en `vendor/duo_ur/duo_ur_real.launch.py` y se monta como overlay **read-only solo en el servicio sim**. Eemil queda pristine; el driver real usa el original (nunca ejecuta ese bloque). Mismo patron que `mir_raw.py`.

### Auto-deteccion del contenedor UR (23-Jun-2026)

`backend/main.py` ya no hardcodea `mir_ur_driver`. La funcion `_ur_container_name()` auto-detecta cual de los dos contenedores UR esta corriendo (`mir_ur_driver` real ↔ `mir_ur_driver_sim`), con override via env `UR_CONTAINER`. Son mutuamente excluyentes (ambos bindean rosbridge :9090), asi que los mismos endpoints `/api/ur/*` sirven para hardware real y para simulacion.

---

## 10. Bugs Encontrados y Corregidos

### Sesion 23-Jun-2026

| Bug | Causa | Estado |
|---|---|---|
| `sim_entrypoint.sh` modificaba el codigo de Eemil | Aplicaba el fix del launch con `sed -i` sobre `/root/workspace` (montado RW del workspace de Eemil). | Corregido: launch parcheado vendorizado en `vendor/duo_ur/` y montado como overlay read-only solo en sim; Eemil restaurado a pristine. |
| El perfil `sim` no servia como banco de pruebas de endpoints | No lanzaba `joint_server` (:9091) y el backend apuntaba al contenedor `mir_ur_driver` hardcodeado. | Corregido: `joint_server` en `sim_entrypoint.sh` + montajes en compose + auto-deteccion de contenedor en backend. |
| `/api/ur/status` reporta `driver_running:true` siempre | `pgrep -f duo_ur` se matchea a si mismo (la cadena "duo_ur" esta en su propia linea de comando). | PENDIENTE. Fix sugerido: `pgrep -f "[d]uo_ur_real"`. |

### Sesion 22-Jun-2026

| Bug | Causa | Solucion |
|---|---|---|
| Joints no se veian en la UI | El intento con rosbridge.js fallaba (QoS mismatch). El intento con docker exec + YAML era lento. | Se creo `joint_server.py`: servidor HTTP en :9091 que se suscribe a /joint_states. Deploy sin reiniciar con docker cp + docker exec -d. |
| scaled_joint_trajectory_controller roto | Acepta goals pero el resultado nunca llega (timeout 15s). Internamente se deadlockea. | Se cambio a `joint_trajectory_controller` estandar. El scaled queda inactivo. |
| joint_mover.py crasheaba con AttributeError | `result_future.result()` retorna None cuando hay timeout. El codigo accedia a `.status` sin verificar. | Se agrego `if result is None` con mensaje claro de error. |
| Backend error 500 con mensaje vacio | `docker exec_run` tenia `stderr=False`, descartando el traceback de Python. | Se cambio a `stderr=True`. El error ahora incluye exit code y output. |
| Robot no se movia (controller decia OK) | `robot_program_running = False` — el script URScript no corria en el robot. El controller reportaba exito porque la tolerancia (0.1 rad) > delta (0.01 rad). | Se agrego `resend_robot_program` en ur_start.sh y en el backend como auto-recovery. |
| Brazo derecho goal rejected | El `right_controller_stopper` desactivaba el controller durante la conexion inicial. | Se agrego loop de reactivacion (3 reintentos) en ur_start.sh y en el backend. |
| UI mostraba "5Hz" vs "400Hz" parpadeante | Dos funciones JS (una REST, otra rosbridge) competian por el mismo label. | Texto unificado: `12 joints @ 400Hz`. |
| launch_dashboard_client default=false | Bug en el launch file de Eemil: `duo_ur_real.launch.py` tiene default `false`. | Se pasa `launch_dashboard_client:=true` explicitamente en ur_start.sh. |

---

## 11. Inventario de Archivos

```
mir_suite/
├── PROJECT.md                       # Este documento (contexto completo)
├── docker-compose.yml               # Orquestacion de contenedores
├── .gitignore
│
├── backend/
│   ├── main.py                      # FastAPI: auth + endpoints + sirve la UI compilada
│   └── requirements.txt             # fastapi, uvicorn, docker, httpx, pydantic
│
├── web/                             # UI nueva (Vite + Svelte 5) — la que se usa
│   ├── src/components/              # Login, Header, CameraPanel, MirPanel, UrPanel, Viewer3D, SkillsPanel, LogPanel
│   ├── src/lib/                     # config, api, auth, joints, ros, skills, log (stores)
│   ├── public/models/              # mallas .dae copiadas de ../models (gitignored, via prebuild)
│   └── package.json, vite.config.js
│
├── frontend/
│   └── index.html                   # UI vieja (JUBILADA — ya no se sirve, queda como referencia)
│
├── scripts/
│   ├── ur_entrypoint.sh             # Entrypoint del contenedor mir_ur_driver
│   ├── ur_start.sh                  # Inicia el driver UR con recovery
│   ├── ur_stop.sh                   # Detiene el driver UR
│   ├── joint_server.py              # HTTP server :9091 para /joint_states
│   ├── joint_mover.py               # Mueve un joint via action client
│   ├── action_bridge.py             # JSON → ROS2 actions (de sesiones anteriores)
│   ├── camera_entrypoint.sh         # Entrypoint del contenedor mir_camera
│   ├── rosbridge_entrypoint.sh      # Entrypoint de rosbridge standalone
│   ├── sim_entrypoint.sh            # Entrypoint para simulacion UR
│   ├── mir_entrypoint.sh            # Entrypoint del contenedor mir_mir
│   ├── mir_raw.py                   # Bridge ROS1→ROS2 de Eemil (sin modificar)
│   ├── mir_watchdog.sh              # Watchdog para auto-recuperacion del bridge
│   └── roslibpy_test.py             # Test de conexion a rosbridge (Eemil)
│
├── docker/
│   ├── ui/Dockerfile                # Imagen mir_ui
│   ├── camera/Dockerfile            # Imagen mir_camera
│   ├── ur_driver/Dockerfile         # Imagen mir_ur_driver
│   ├── mir/Dockerfile               # Imagen mir_mir
│   ├── base/                        # Imagen base ros2humble_dev
│   ├── moveit/                      # Config MoveIt
│   └── rosbridge/                   # Rosbridge standalone
│
├── config/
│   └── right_safe_pose.json         # Pose segura del brazo derecho
│
├── vendor/                          # Copias parcheadas de archivos de terceros (no se toca el original)
│   └── duo_ur/
│       └── duo_ur_real.launch.py    # Launch de Eemil parcheado para fake_hardware (overlay solo en sim)
│
├── models/                          # Mallas 3D UR5e para Three.js
│   ├── ur5e_base.dae
│   ├── ur5e_shoulder.dae
│   ├── ur5e_upperarm.dae
│   ├── ur5e_forearm.dae
│   ├── ur5e_wrist1.dae
│   ├── ur5e_wrist2.dae
│   ├── ur5e_wrist3.dae
│   └── ur5e_chain.json
│
├── docs/
│   ├── mir_integration.md           # Documentacion inicial del MiR
│   ├── mir_connectivity_issue.md    # Diagnostico de conectividad MiR
│   ├── joints_display_fix.md        # Documentacion del fix de joints
│   ├── AVANCE_JUNTA.md              # Avance y preguntas para el asesor
│   ├── EXTERNAL_PROJECTS.md         # Referencia a proyectos externos
│   └── comandos.txt                 # Comandos utiles
│
├── reports/
│   ├── architecture.html            # Mapa de arquitectura visual
│   ├── component_diagram.html       # Diagrama de componentes del robot
│   ├── network_topology.html        # Topologia de red visual
│   ├── reporte_mir_suite_22jun2026.html   # Reporte combinado (espanol)
│   ├── reporte_mir200_es.html       # Reporte solo MiR (espanol)
│   ├── reporte_brazos_ur5e_es.html  # Reporte solo brazos (espanol)
│   ├── session_report_22jun2026.html      # Reporte tecnico (ingles)
│   └── session_report_22jun2026_es.html   # Reporte largo (espanol)
│
└── logs/                            # Logs persistentes de contenedores
```

---

## 12. Comandos de Operacion

### Iniciar todo el sistema

```bash
cd /home/lab/Desktop/MIR/mir_suite
docker compose down
docker compose up -d
```

### Iniciar con perfil de brazos

```bash
docker compose --profile arms up -d
```

### Acceso a la UI

Abrir en un navegador (en la red local del lab): **`http://tunisuite.local`** (o `http://192.168.1.75`).
Login: `admin` / `admin`. El nombre `tunisuite.local` lo publica Kevin por mDNS
(`avahi-publish`, con entrada `@reboot` en el crontab para que persista).

### Ver logs

```bash
docker logs -f mir_ui
docker logs -f mir_ur_driver
docker logs -f mir_camera
docker logs -f mir_mir
```

### Controlar el driver UR desde linea de comandos

Los `/api/*` exigen el token de auth. Primero hay que loguearse:

```bash
# Obtener el token
TOK=$(curl -s -X POST http://localhost/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")

# Iniciar / detener el driver
curl -X POST http://localhost/api/ur/start -H "X-MIR-Token: $TOK"
curl -X POST http://localhost/api/ur/stop  -H "X-MIR-Token: $TOK"

# Ver estado / joints
curl http://localhost/api/ur/status -H "X-MIR-Token: $TOK"
curl http://localhost/api/ur/joints -H "X-MIR-Token: $TOK" | python3 -m json.tool

# Mover codo izquierdo +0.1 rad
curl -X POST http://localhost/api/ur/move -H "X-MIR-Token: $TOK" \
  -H "Content-Type: application/json" \
  -d '{"arm":"left","joint":"elbow","delta":0.1}'
```

### Reconstruir un contenedor

```bash
# UI (multi-stage: compila la UI Svelte y la hornea en la imagen)
docker build --network host -t mir_ui:latest -f docker/ui/Dockerfile . && \
  docker compose up -d mir_ui

# UR driver
docker build --network host -t mir-ur-driver:latest -f docker/ur_driver/Dockerfile . && \
  docker tag mir-ur-driver:latest mir-ur-driver:latest && \
  docker stop mir_ur_driver && docker rm mir_ur_driver && \
  docker compose --profile arms up -d ur_driver
```

### Desplegar sin reiniciar el contenedor

```bash
# Copiar un script al contenedor corriendo
docker cp scripts/nuevo_script.py mir_ur_driver:/nuevo_script.py

# Ejecutarlo en background sin bloquear
docker exec -d mir_ur_driver bash -c "source setup.bash && python3 /nuevo_script.py &"
```

### Verificar estado de los brazos

```bash
# Joints en vivo
docker exec mir_ur_driver bash -c "source /opt/ros/humble/setup.bash && source /root/workspace/ros_ws/install/setup.bash && ros2 topic hz /joint_states"

# Controladores activos
docker exec mir_ur_driver bash -c "source /opt/ros/humble/setup.bash && ros2 control list_controllers"

# Modo del robot
docker exec mir_ur_driver bash -c "source /opt/ros/humble/setup.bash && source /root/workspace/ros_ws/install/setup.bash && ros2 topic echo /left_io_and_status_controller/robot_mode --field mode"

# Reenviar programa de control
docker exec mir_ur_driver bash -c "source /opt/ros/humble/setup.bash && ros2 service call /left_io_and_status_controller/resend_robot_program std_srvs/srv/Trigger"
```

---

## 13. Proximos Pasos

### Prioridad Inmediata

1. **MiR200:** Que un tecnico revise fisicamente el robot. Hacer reinicio completo (Shutdown, esperar 1 minuto, encender). Si los errores 9000 persisten, contactar soporte MiR.
2. **Nordbo F/T:** Integrar los 2 sensores de fuerza/torque (192.168.1.112/113) en la UI. Eemil ya tiene `dual_nordbo.launch.py` listo.
3. **Probar otros joints:** Verificar que shoulder_pan, shoulder_lift, wrist_1, wrist_2, wrist_3 tambien responden a comandos (con el mismo approach conservador).

### Prioridad Media

4. **Home position:** Boton en la UI que mande ambos brazos a una posicion segura predefinida. Ya existe `config/right_safe_pose.json` y `action_bridge.py` tiene comandos home.
5. **Trayectorias completas:** Probar MoveIt para planificar y ejecutar trayectorias Cartesianas.
6. **Reactivar bridge MiR:** Cuando el MiR este estable, levantar `mir_mir` para recibir telemetria ROS en tiempo real (robot_pose, scan, odom, etc.).
7. **Panel de control completo:** Agregar botones para todos los joints, slider de velocidad, boton de emergencia.

### Documentacion

8. **HTML para el tutor:** El reporte combinado `reports/reporte_mir_suite_22jun2026.html` cubre todo lo hecho. Actualizar cuando haya nuevo avance.

---

## 14. Preguntas para el Tutor

1. El MiR200 tiene errores de seguridad criticos (codigo 9000: SICK Safety PLC + Emergency Stop). Requiere intervencion fisica. Hay alguien que pueda revisarlo esta semana o debemos contactar soporte MiR?

2. Los brazos UR5e son PolyScopeX (software nuevo de UR), no e-Series. Esto significa que el servidor de dashboard (servicios de recovery) no existe. Para recuperar de un error hay que hacerlo manualmente desde la tablet del brazo. Es esto esperado?

3. Ahora que los codos se mueven desde la UI, debemos expandir a otros joints o primero probar trayectorias completas con MoveIt?

4. Podemos hacer las pruebas de integracion completas (MiR + brazos + camara) en simulacion mientras el MiR se repara? Eemil tiene `duo_ur_sim.launch.py` listo.

5. Los sensores Nordbo de fuerza/torque (192.168.1.112 y 113) ya responden en la red. Es buen momento para integrarlos en la UI, o priorizamos otra cosa?

---

## 15. Reglas del Proyecto

Ver tambien: `/home/lab/Desktop/MIR/rules.md`

1. **Seguridad primero:** MiR200 siempre apagado a menos que se autorice explicitamente. Brazos UR5e sin movimientos bruscos.
2. **Aislamiento:** NUNCA modificar archivos en `pandai_ark/`, `pbd_system/`, `teleop/`, `ur_ws/`, `aiprism_ws/`. Todo nuestro trabajo vive en `mir_suite/`.
3. **Documentacion:** Cada paso, descubrimiento y cambio de configuracion se registra en `memory.md` (bitacora) y `PROJECT.md` (este documento, referencia).
4. **Web-first:** La UI debe ser accesible via navegador sin instalar ROS.
5. **Docker-native:** Todo nuevo componente debe estar containerizado.
6. **network_mode: host:** Obligatorio por limitacion del kernel Jetson (sin iptables raw).
7. **Codigo en ingles, documentacion en espanol:** Los comentarios en el codigo van en ingles. La documentacion (memory.md, PROJECT.md, docs, reportes) va en espanol.
8. **Sin emojis en la UI ni en reportes:** Documentos profesionales, colores Tampere University.
9. **Control manual de servicios criticos:** El driver UR no se inicia solo. El usuario lo activa desde la UI cuando este listo.

---

*Documento mantenido por Kevin (estudiante) con asistencia de opencode.*
*Ultima actualizacion: 22 de junio de 2026, sesion de integracion de brazos UR5e.*
