# Diagnóstico del MiR200 — 2026-06-29

Sesión de inmersión profunda en el MiR200 (`MiR_S455`) para entender su
inestabilidad. Resumen: **el MiR está sano; el problema de fondo es la señal
WiFi**, y de paso se arregló un bug propio en el watchdog del bridge.

---

## 1. Acceso al MiR (cómo se diagnostica)

- **REST API:** `http://<ip>/api/v2.0.0` — autenticación
  `Authorization: Basic base64(usuario:sha256_hex(contraseña))`.
- **Credenciales:** `admin` / `admin` (funcionan).
- `/api/v2.0.0/status` es **público** (sin auth); el resto pide auth.
- Puertos abiertos: 80, 443, 8080, **9090 (rosbridge)**, 22 (SSH).
- Endpoints útiles vistos: `/status`, `/system/info`, `/metrics`, `/registers`,
  `/settings`, `/settings/advanced`, `/maps`, `/missions`, `/wifi/connections`.

Generador del header de auth (bash):
```bash
H="Authorization: Basic $(printf 'admin:%s' \
   "$(printf admin | sha256sum | cut -d' ' -f1)" | base64 -w0)"
curl -s -H "$H" http://192.168.1.13/api/v2.0.0/system/info
```

---

## 2. Estado de salud (todo OK salvo el WiFi)

| Área | Valor | Veredicto |
|---|---|---|
| Software MiR | **2.13.3.2**, modelo MIR200, PC NUC (BIOS 2017) | Antiguo pero estable |
| Errores activos | `errors: []`, `mir_robot_errors 0` | 🟢 Limpio (los ~9000 de antes eran históricos) |
| Batería | ~85% (~11 h restantes) | 🟢 |
| Localización | `localization_score 0.28` (0 = perfecto) | 🟢 |
| rosbridge :9090 | Vivo, responde servicios | 🟢 (cuando hay red) |
| **WiFi señal** | **−86 a −88 dBm** en 5 GHz | 🔴 **Causa raíz #1** |
| Reloj | **Feb 2016** (~10 años de desfase) | 🟡 NTP no sincroniza |

---

## 3. Causa raíz #1 — WiFi marginal (5 GHz, −87 dBm)

- El MiR se conecta por WiFi (adaptador `wlp2s0`) a la SSID **`RUT_D572_5G`**
  (Teltonika, banda 5 GHz). RSSI medido: **−86/−87/−88 dBm** = muy débil.
- 5 GHz tiene mucho menos alcance/penetración que 2.4 GHz → a esa distancia el
  enlace queda al filo.
- **Observado EN VIVO durante la sesión:** el MiR **se cayó de la red por
  completo** (`ARP FAILED`, REST `HTTP 000`) y **no reasoció solo en +70 s**.
  Esa es la inestabilidad ocurriendo en directo.
- El síntoma documentado "el rosbridge del MiR se cuelga con frecuencia" se
  explica en gran parte por esto: cuando el WiFi degrada, `roslibpy` da
  `RosTimeoutError: Failed to connect to ROS`, y cuando cae del todo, ni el
  handshake WebSocket crudo conecta (`No route to host`).
- Cuando el enlace está bien, todo funciona: 25/25 sondas REST OK a 6–21 ms,
  15/15 handshakes WS OK a 4–9 ms, y el bridge republica `/odom` a ~3–4 Hz.

**Cura de fondo:** pasar el MiR a **2.4 GHz** (misma red Teltonika, mejor
alcance) o mejorar la cobertura del AP. 2.4 GHz a la misma distancia suele dar
~10–15 dB mejor (de −87 a ~−73, ya usable).

### Bloqueo actual (acción pendiente con Wael)
- En la lista de redes del MiR **solo aparece `RUT_D572_5G`** (no hay SSID
  2.4 GHz visible), y **no tenemos la contraseña** de la red Teltonika.
- **PREGUNTA PARA WAEL:** ¿se puede habilitar la SSID de **2.4 GHz** en la
  Teltonika (`RUT_D572`) y/o darnos la **contraseña** del WiFi, para conectar
  el MiR a 2.4 GHz? (La 2.4 y la 5 GHz suelen compartir contraseña.)

### Importante sobre la red (no usar dd-wrt)
- El host **Kevin** está cableado a la **Teltonika** (`192.168.1.75`, ifaces
  `lan2`/`lan4`). **No** está en la red `dd-wrt` (`192.168.12.x`).
- Si el MiR se conecta a dd-wrt obtiene una IP `192.168.12.x` que **Kevin no
  rutea** (la manda por la salida a internet) → **la suite no lo ve**.
- Regla: **el MiR debe estar en la misma red que Kevin → la Teltonika
  `192.168.1.x`** (idealmente su SSID de 2.4 GHz). IP esperada: `192.168.1.13`.

---

## 4. Bug propio encontrado y arreglado — watchdog del bridge

### El problema
El watchdog viejo (`mir_watchdog.sh`) medía "actividad" leyendo el **stdout**
de `mir_raw.py`. Pero el nodo se llama `rosbridge_explorer`, así que **todas**
sus líneas de log contienen `[rosbridge_explorer]:` — y el `entrypoint`
**excluía justo esas líneas** de refrescar el heartbeat. Resultado:

- En operación normal **nada** refrescaba el timestamp → a los 90 s el watchdog
  creía que estaba "mudo" y **mataba un bridge sano**.
- Cada reinicio forzado generaba **churn de conexiones** al rosbridge del MiR,
  que contribuye a colgarlo. El watchdog "de seguridad" **causaba** parte de la
  inestabilidad que debía evitar.

### El arreglo (sin tocar el código de Eemil `mir_raw.py`)
1. **`scripts/mir_liveness.py`** (nuevo): nodo ROS2 que se suscribe a `/odom`
   (publica ~3.5 Hz incluso en Pause) y refresca el heartbeat
   `/tmp/mir_bridge_last_io` con **datos reales** del camino completo
   MiR→bridge→ROS2. Solo suscribe; nunca comanda el robot.
2. **`scripts/mir_watchdog.sh`** (reescrito):
   - **Ventana de gracia de arranque** (`MIR_WATCHDOG_STARTUP_GRACE`, 60 s):
     `mir_raw.py` tarda ~25–30 s en descubrir los tipos de topic antes de
     republicar nada, así que no se juzga "mudo" a un bridge recién lanzado.
   - **Umbral de mudez** (`MIR_WATCHDOG_THRESHOLD`, 25 s) sobre el heartbeat.
   - **Sonda con 3 reintentos** al rosbridge del MiR para distinguir si el
     cuelgue es del **MiR** o de **nuestro cliente** (un solo intento daba
     falsos negativos por el WiFi marginal).
3. **`scripts/mir_entrypoint.sh`** (reescrito): lanza el nodo liveness, marca
   cada (re)arranque del bridge para la gracia, y quita el touch-por-stdout roto.
4. **`docker-compose.yml` / `docker/mir/Dockerfile`**: se montan/copian los dos
   archivos nuevos (`mir_watchdog.sh`, `mir_liveness.py`).

### Validado en vivo
- Arranque: el bridge sobrevive el descubrimiento (no lo matan en la gracia),
  `/odom` empieza a fluir (~45 s) y el heartbeat se queda fresco (<1 s).
- Estado estable: **0 kills** del watchdog con el bridge sano.
- Recuperación real: al **congelar** el bridge (`SIGSTOP`, simula "vivo pero
  mudo"), el watchdog lo detectó (MUTE 40 s) y lo reinició solo. ✅

### Variables de entorno (tuneables)
| Var | Default | Qué hace |
|---|---|---|
| `MIR_WATCHDOG_STARTUP_GRACE` | 60 | Gracia tras (re)arranque del bridge (s) |
| `MIR_WATCHDOG_THRESHOLD` | 25 | Mudez de `/odom` para declarar cuelgue (s) |
| `MIR_WATCHDOG_INTERVAL` | 15 | Cada cuánto corre el watchdog (s) |
| `MIR_LIVENESS_TOPIC` | `/odom` | Topic usado como señal de vida |

---

## 5. Otros hallazgos menores

- **Reloj en 2016:** la fecha del sistema del MiR está ~10 años atrás (NTP no
  sincroniza). Cosmético, pero ensucia timestamps de logs y validaciones.
  Pendiente: apuntarlo a un NTP (la Teltonika) o ajustarlo.
- **`/metrics` es mínimo** en software 2.13 (solo batería, uptime, errores,
  WiFi, posición); no expone CPU/temperatura/motores.
- Los "logs" de `/software/logs` son solo el **historial de actualizaciones de
  firmware** (2.1.0 → … → 2.13.3.2), no logs de errores.

---

## 6. Estado y próximos pasos

| Tarea | Estado |
|---|---|
| Resiliencia del bridge (watchdog/liveness) | ✅ **Hecho y validado** |
| WiFi → 2.4 GHz | ⛔ **Bloqueado** — falta habilitar SSID 2.4 GHz / contraseña (Wael) |
| Arreglar reloj/NTP del MiR | ⏳ Pendiente |
| Reactivar telemetría MiR en la UI (`/robot_pose`, `/scan`, `/odom`) | ⏳ Pendiente (depende de red estable) |

**Acción inmediata:** preguntar a **Wael** si podemos (a) habilitar la SSID de
2.4 GHz de la Teltonika `RUT_D572` y (b) tener la contraseña del WiFi, para
mover el MiR a 2.4 GHz en la red `192.168.1.x` (donde vive Kevin).
