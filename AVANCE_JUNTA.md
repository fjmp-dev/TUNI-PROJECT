# MIR Suite — Avance y Preguntas para el Asesor

**Fecha:** 15 Junio 2026
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
- Botón de EMERGENCY STOP funcional
- Conexión/desconexión automática

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

### Sobre el alcance final
1. "La meta es una suite donde el investigador elija qué componentes levantar, idealmente desde la UI web. ¿Esto es lo que esperan, o basta con docker-compose + profiles bien documentados?"
2. "¿Hay otros investigadores que ya estén usando el robot y tengan necesidades específicas que debamos cubrir?"
3. "El MiR200 está en otra subred (192.168.12.x). ¿Hay plan para integrarlo a la red 192.168.1.x o usamos la API REST directo a su IP?"

### Sobre tiempos y prioridades
4. "¿Cuál es la prioridad para las próximas semanas: pulir el 3D, integrar el MiR200, o hacer el dashboard de lanzamiento de servicios?"
5. "¿Hay fecha límite o entregable concreto para este proyecto?"

### Sobre infraestructura
6. "La SIM 4G/5G del router — ¿cuándo se instala? Eso habilitaría acceso remoto."
7. "El segundo acelerador (ACCELERATOR 2 en el diagrama) y el ENDEFFER (BrainCo Hand) — ¿están operativos? ¿Debemos dockerizarlos también?"

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
