# MiR200 - Diagnóstico de Problemas de Conectividad

**Fecha:** 22 de junio de 2026
**Autor:** Kevin (estudiante) + Claude (asistente)
**Robot:** MiR200 (MiR_S455), IP 192.168.1.13, MAC 34:41:5d:3e:55:f3
**Workspace:** `/home/lab/Desktop/MIR/mir_suite`

---

## 1. Resumen Ejecutivo

El robot MiR200 presenta **dos problemas distintos e interrelacionados**:

1. **Problema de red intermitente** — La interfaz de red del robot se cae y vuelve a estar disponible cíclicamente
2. **Errores de seguridad persistentes (código 9000)** — El robot entra en estado "Error" cuando le damos "Play" porque sus sistemas de seguridad internos no responden

**Impacto:** Imposible recibir datos de telemetría del robot en tiempo real (`/robot_pose`, `/scan`, `/odom`, `/MC/battery_percentage`, `/mir_status_msg`) cuando está activo. Solo es posible obtener datos básicos via REST API (batería, posición, errores) cuando el robot está en estado "Pause".

---

## 2. Inventario del Robot

| Atributo | Valor |
|---|---|
| Modelo | MiR200 |
| Nombre | MiR_S455 |
| IP | 192.168.1.13 |
| MAC | 34:41:5d:3e:55:f3 |
| Gateway | 192.168.1.1 (Teltonika) |
| DNS | 8.8.8.8, 8.8.4.4 |
| Versión firmware | (desconocida, no respondía cuando intentamos consultarla) |
| Batería observada | 65-69% durante las pruebas |

---

## 3. Topología de Red

```
                    [Internet]
                        |
                  195.148.48.1 (gateway público)
                        |
              +---------+---------+
              |    lan1 (Kevin)    |  195.148.48.186
              |  Jetson AGX Orin  |
              |    (Kevin)        |
              +---------+---------+
                        |
              192.168.1.1 (gateway LAN)
                        |
              +---------+---------+-------+
              |         |         |       |
         192.168.1.13  192.168.1.75  192.168.1.112  192.168.1.113
            [MiR]      [Kevin]      [Nordbo1]     [Nordbo2]
                                          + 192.168.1.102/103 (UR5e arms, apagados)
```

**Kevin tiene dos interfaces en la misma subred 192.168.1.0/24:**
- `lan2` y `lan4` ambas con IP 192.168.1.75
- Esto causa ARP flux (cambia qué interfaz se usa para cada destino)
- No afecta la comunicación con el MiR pero puede causar confusión

---

## 4. Pruebas Realizadas

### 4.1. Estado del robot según REST API

**Endpoint:** `GET http://192.168.1.13/api/v2.0.0/status`

**Síntomas observados en el ciclo:**

| Momento | Estado | Battery | Errores | Notas |
|---|---|---|---|---|
| Inicio (Pause) | Pause | 69.9% | 0 | Funciona |
| Después de Play | Error | 65.4% | 2 (cód 9000) | Red colapsa |
| Re-pause | Pause | 65.4% | 2 | Red vuelve a responder |
| Re-play | Error | 65.4% | 2 | Red colapsa de nuevo |

### 4.2. Errores observados

**Error 1:** `code 10713: "Large encoder delay detected!"` del módulo **Motorcontroller**
- Error de las ruedas/encoders (problema físico, conocido del MiR200)
- Aparece cuando el cable del encoder está cerca de una rueda o suelto

**Error 2:** `code 9000: Missing - "SICK Safety PLC is OK"` del módulo **Safety System/Communication**
- El PLC de seguridad SICK no responde a heartbeats

**Error 3:** `code 9000: Missing - "Emergency Stop is OK"` del módulo **Safety System/Emergency Stop**
- El botón de emergencia no responde a heartbeats

### 4.3. Comportamiento de la red

| Servicio | En Pause | En Play | Notas |
|---|---|---|---|
| Ping (ICMP) | Bloqueado* | Bloqueado* | *ICMP bloqueado por firewall del MiR (normal) |
| REST API :80 | OK (88-200ms) | CAE | HTTP 200 → HTTP 000 |
| rosbridge :9090 | OK (algunos seg) | CAE | "No route to host" |
| SSH :22 | OK (al abrir conexión) | CAE | "No route to host" |
| ARP | A veces responde | No responde | MAC 34:41:5d:3e:55:f3 desaparece |

**Patrón clave:** Cuando el robot está en Pause, los servicios web están disponibles brevemente (3-10s) y luego colapsan. Cuando le damos Play, colapsan inmediatamente. Cuando re-pausamos, vuelven a estar disponibles.

### 4.4. Tráfico de topics ROS

| Estado | Topics descubiertos | Topics publicando |
|---|---|---|
| Pause | ~2-10 | 0 (el robot no publica) |
| Play (transitorio) | 132-199 | Algunos (inestable) |
| Robot en Error | 132 | 0 (no publica por estar en Error) |

### 4.5. Bridge ROS1→ROS2 (`mir_mir`)

**Comportamiento observado:** El bridge `mir_raw.py` (escrito por Eemil) **no maneja la desconexión del MiR rosbridge**. Cuando el robot colapsa, el bridge queda "vivo pero sin datos" — el proceso Python sigue ejecutando `rclpy.spin()` pero nunca recibe más mensajes. El proceso consume CPU y memoria sin hacer nada útil.

**Solución implementada:** Watchdog externo que mata el bridge si pasan 90 segundos sin actividad en el log, y el entrypoint lo relanza automáticamente. Cero modificaciones al código de Eemil.

---

## 5. Causa Raíz (Hipótesis)

### 5.1. Causa primaria

**El robot MiR200 tiene un problema de hardware en su PLC de seguridad SICK o en la cadena del botón de emergencia.** Esto causa:

1. El robot entra en estado "Error" cuando intenta activar sus subsistemas (modo Running)
2. El estado "Error" sobrecarga el sistema operativo interno
3. La sobrecarga colapsa los servicios de red (rosbridge, REST API, SSH)
4. Cuando re-pausamos, los servicios vuelven a estar disponibles brevemente

### 5.2. Causa secundaria

**El bridge `mir_raw.py` no maneja desconexiones**, lo que hace que tengamos que reiniciarlo manualmente cuando el robot colapsa. Esto ya está arreglado con el watchdog.

### 5.3. Causa terciaria (potencial)

**El cable del encoder (error 10713) puede estar relacionado con el problema de seguridad**, ya que ambos son problemas de hardware interno del robot. Es posible que cuando el robot detecta el error del encoder, también detecte problemas de comunicación con los sistemas de seguridad.

---

## 6. Soluciones Intentadas

| # | Acción | Resultado |
|---|---|---|
| 1 | Restart del contenedor `mir_mir` (bridge) | Recuperó la conexión temporalmente |
| 2 | Múltiples toggles Pause/Play desde la tablet | El robot colapsa la red cada vez que entra en Play |
| 3 | Watchdog automático en el bridge | Resuelve el problema secundario (bridge auto-recupera) |
| 4 | Cache de 60s en el proxy REST | Resuelve parpadeo en la UI cuando hay timeouts cortos |
| 5 | Verificar cables Ethernet del MiR | Sin problemas visibles (cable conectado) |

---

## 7. Solución Recomendada (para el tutor)

**El problema requiere intervención física en el robot:**

1. **Reinicio físico completo del robot:**
   - Service → Shutdown desde la tablet
   - Esperar 1 minuto (capacitores del PLC de seguridad)
   - Encender con botón físico lateral
   - Esperar 2-3 minutos al boot

2. **Si el error 9000 persiste después del reinicio:**
   - Revisar las conexiones internas del SICK Safety PLC
   - Verificar el cable del botón de emergencia
   - Considerar reemplazo del PLC si el firmware está corrupto

3. **Para el error 10713 (encoder):**
   - Revisar el cable del encoder de las ruedas
   - Verificar que no esté rozando con las ruedas
   - Posible recalibración desde el menú Service

4. **Como último recurso:**
   - Contactar soporte MiR
   - El robot puede tener daño físico en la cadena de seguridad

---

## 8. Estado Actual del Sistema

### 8.1. Lo que SÍ funciona

- **REST API** del MiR (en Pause): `GET /api/v2.0.0/status` retorna JSON con estado, batería, posición, errores
- **Módulo MiR en la UI web** (`http://localhost:8080`): muestra datos via REST API, con cache de 60s
- **Bridge `mir_mir`**: auto-recupera con watchdog cuando se cuelga
- **Topics ROS2 del MiR**: 132 topics descubiertos, listos para recibir datos cuando el robot esté OK
- **Cámara Orbbec** (separada): funciona independiente, 30Hz
- **Nordbo F/T** (sensores): ambos responden, listos para integrar

### 8.2. Lo que NO funciona

- **Datos en tiempo real** del MiR (robot_pose, scan, odom, etc.) por problemas de red
- **Modo Running** del MiR: colapsa la red
- **Recibir errores en vivo**: solo podemos verlos via REST cuando el robot está en Pause

### 8.2. Servicios Docker activos

```
mir_ui          Up    :8080  (Web UI + proxy REST MiR)
mir_mir         Up    -       (Bridge ROS1↔ROS2 del MiR con watchdog)
mir_camera      Up    -       (Orbbec Gemini 330)
mir_ur_driver   Up    :9090, 50001-50014 (UR5e driver + MoveIt + rosbridge)
```

---

## 9. Preguntas para el Tutor

1. **¿Vale la pena seguir intentando recuperar este MiR o es mejor reemplazarlo?**
2. **¿Hay otro MiR disponible en el laboratorio que podamos usar?**
3. **¿Podemos saltarnos el MiR y hacer las pruebas de integración directamente con simulación (UR5e + Nordbo + cámara en Gazebo)?**
4. **¿Hay un procedimiento documentado de "reinicio profundo" del MiR200 para cuando los servicios web colapsan?**
5. **¿El error 10713 (encoder) es causa o efecto del error 9000 (safety)?**

---

## 10. Lecciones Aprendidas

1. **Los robots MiR200 son sensibles a problemas internos de hardware** — Cuando hay un error físico, la red se cae antes que los sistemas de seguridad
2. **El estado "Pause" es más que un estado lógico** — También afecta a los servicios de red del robot
3. **El bridge de Eemil es robusto en la conexión inicial pero no maneja desconexiones** — Necesita un watchdog externo
4. **REST API es más estable que rosbridge** — Cuando el robot colapsa, REST dura un poco más
5. **El cache en la UI es esencial** — Sin él, la UI parpadea constantemente entre estados

---

## 11. Archivos del Proyecto Involucrados

| Archivo | Descripción |
|---|---|
| `mir_suite/scripts/mir_raw.py` | Bridge ROS1→ROS2 de Eemil (NO modificado) |
| `mir_suite/scripts/mir_entrypoint.sh` | Entrypoint con watchdog (modificado) |
| `mir_suite/scripts/mir_watchdog.sh` | Watchdog nuevo (creado) |
| `mir_suite/docker/mir/Dockerfile` | Imagen del contenedor mir_mir (modificado) |
| `mir_suite/backend/main.py` | Proxy REST `/api/mir/status` con cache (modificado) |
| `mir_suite/frontend/index.html` | Módulo MiR en UI con manejo de stale (modificado) |
| `mir_suite/docs/mir_integration.md` | Documentación inicial del MiR |
| `memory.md` | Bitácora principal del proyecto (actualizado) |
