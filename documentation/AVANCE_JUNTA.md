# MIR Suite — Avance y Preguntas para el Asesor

**Fecha:** 22 Junio 2026
**Proyecto:** Suite de software modular para MIR + UR5e

---

## Lo que ya está funcionando






### Infraestructura Docker
- 3 contenedores modulares (`mir_ui`, `mir_camera`, `mir_ur_driver`)
- `docker-compose.yml` con profiles: `--profile vision`, `--profile arms`, `--profile full`
- Cada componente es independiente y reiniciable sin tumbar los demás
- Logs persistentes en `logs/`

### Comunicación en tiempo real
- Web UI accesible desde cualquier navegador en `http://192.168.1.75:8080`
- ROSBridge (WebSocket) en puerto 9090


- `/joint_states` → 12 articulaciones de AMBOS brazos en vivo (500 Hz)
- Cámara Orbbec → feed JPEG en vivo (30 fps, 1280x800)

### Web UI funcional



- Panel izquierdo: ángulos de las 6 articulaciones del brazo izquierdo
- Panel derecho: ángulos de las 6 articulaciones del brazo derecho
- Panel de cámara: video en vivo de la Orbbec
- **Panel MiR (nuevo)**: batería con barra de color, posición, velocidad, estado (Pause/Ready/Running/Error), modo, misión, errores. Polling REST cada 4s.
- Botón de EMERGENCY STOP funcional
- Conexión/desconexión automática

### Integración MiR200 (REST API)

- Endpoint backend `GET /api/mir/status` (proxy a `192.168.1.13/api/v2.0.0/status`) con cache de 60s
- Bridge ROS1↔ROS2 en contenedor `mir_mir` (roslibpy + rclpy, 132 topics descubiertos)
- Watchdog automático que reinicia el bridge si se queda "vivo pero sin datos" (90s sin actividad)
- Funciona en Pause (datos básicos) — datos ROS en tiempo real solo con robot activo

### Problema conocido: MiR200 inestable en modo Running

- **Causa:** El robot tiene errores de seguridad persistentes (cód 9000: SICK Safety PLC + Emergency Stop)
- **Síntoma:** Red del robot colapsa al entrar en Play, vuelve a responder al re-pausar
- **Impacto:** Imposible recibir telemetría en tiempo real (`/robot_pose`, `/scan`, `/odom`)
- **Solución temporal:** Trabajamos con REST API en Pause
- **Documentación completa:** `docs/mir_connectivity_issue.md`
- **Preguntas para el asesor:** Ver sección "Preguntas para el asesor" al final

### Integración UR5e Brazos (22-Jun-2026)

- **Driver UR funcionando** con los 2 brazos (left 192.168.1.102, right 192.168.1.103)
- `/joint_states` publica a 387-450 Hz con 12 joints
- **Control manual desde la UI**: botones "Start driver" / "Stop driver" (no se inicia automáticamente)
- **Panel UR en la UI**: muestra 6 valores numéricos por brazo, actualizándose 5 veces/segundo
- **Servidor HTTP persistente** `joint_server.py` (puerto 9091) para evitar docker exec por petición
- **Endpoints backend**: `/api/ur/status`, `/api/ur/start`, `/api/ur/stop`, `/api/ur/joints`
- **Documentación:** `docs/joints_display_fix.md`

### Bug crítico encontrado: `duo_ur_real.launch.py` tiene `launch_dashboard_client` default = `false`
- Hace que los `dashboard_client_node_1` y `_2` NUNCA se lancen
- Fix en `scripts/ur_start.sh`: pasar `launch_dashboard_client:=true` explícitamente
- **Nota:** Robots son PolyScopeX, el dashboard_client se sale con warning (no es e-Series), pero al menos ahora se intenta

### Bug menor en UI: Hz parpadeante (5↔400)
- Causa: dos funciones (REST + rosbridge) actualizaban el mismo label
- Fix: ahora muestra "12 joints @ 400Hz (age X.XXs)" consistentemente

### Codebase
- ~15 archivos, bien documentados (código en inglés, docs en español)
- `PLAN.md` con guía completa de construcción paso a paso
- `memory.md` con bitácora de todas las sesiones

---

## Lo que está en progreso

### Visor 3D
- Código JavaScript completo con Three.js + ColladaLoader
- 7 mallas 3D del UR5e (base, shoulder, upperarm, forearm, wrist1-3)
- Las mallas cargan correctamente (12/12)
- **Bloqueo:** WebGL no funciona en Chromium Snap de la Jetson AGX Orin
- **Soluciones posibles:** instalar Firefox (GLX nativo), o Chromium .deb, o usar `--ozone-platform=wayland`

---

## Preguntas para el asesor

### Sobre el MiR200 (urgente - problema nuevo)

1. **"El robot MiR200 (192.168.1.13) tiene errores de seguridad persistentes (cód 9000: SICK Safety PLC y Emergency Stop no responden). La red del robot colapsa cuando le damos Play. ¿Es problema de hardware conocido? ¿Hay procedimiento de reinicio profundo?"**
   - Documentación completa: `docs/mir_connectivity_issue.md`

2. **"¿Vale la pena seguir intentando recuperar este MiR o es mejor reemplazarlo por otro?"**
   - El robot tiene 2 errores: 10713 (encoder de rueda) + 9000 (safety PLC)

3. **"¿Podemos saltarnos el MiR y hacer pruebas de integración con simulación mientras tanto (UR5e + Nordbo + cámara en Gazebo)?"**

### Sobre el alcance final
4. "La meta es una suite donde el investigador elija qué componentes levantar, idealmente desde la UI web. ¿Esto es lo que esperan, o basta con docker-compose + profiles bien documentados?"
5. "¿Hay otros investigadores que ya estén usando el robot y tengan necesidades específicas que debamos cubrir?"

### Sobre tiempos y prioridades
6. "¿Cuál es la prioridad para las próximas semanas: pulir el 3D, integrar el MiR200, o hacer el dashboard de lanzamiento de servicios?"
7. "¿Hay fecha límite o entregable concreto para este proyecto?"

### Sobre infraestructura
8. "La SIM 4G/5G del router — ¿cuándo se instala? Eso habilitaría acceso remoto."
9. "El segundo acelerador (ACCELERATOR 2 en el diagrama) y el ENDEFFER (BrainCo Hand) — ¿están operativos? ¿Debemos dockerizarlos también?"

---

## Preguntas sobre el diagrama (mir_diag.json)

El diagrama muestra 2 aceleradores:
- **ACCELERATOR 1** = Kevin (Jetson AGX Orin) corriendo ROS2
- **ACCELERATOR 2** = ¿otra Jetson/PC?

"¿El ACCELERATOR 2 ya existe? ¿Qué corre ahí? ¿Debemos integrarlo en nuestra suite?"

---

## Métricas para mostrar

| Métrica | Valor |
|---------|-------|
| Contenedores | 3 (mir_ui 184MB, mir_camera 10.1GB, mir_ur_driver 11.4GB) |
| Joints en vivo | 12 (ambos brazos) |
| Frecuencia joints | ~500 Hz |
| Cámara | 30 fps, 1280x800 |
| Archivos de código | ~15 |
| Días de desarrollo | 4 sesiones (8-12 Jun) |
