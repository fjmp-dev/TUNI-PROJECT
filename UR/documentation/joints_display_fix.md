# Joints Display - Diagnóstico y Solución

**Fecha:** 22 de junio de 2026
**Problema:** El panel UR5e en la UI mostraba "--" en lugar de los valores de los 12 joints
**Síntomas en el navegador:** Console errors `504` en `/api/ur/joints`, valores de joints vacíos

---

## Resumen Ejecutivo

El robot UR5e SÍ estaba publicando `/joint_states` correctamente a 400Hz (verificado con `ros2 topic hz` y por WebSocket directo a rosbridge). El problema era del lado de la UI:

1. La primera versión usaba una suscripción a rosbridge que fallaba silenciosamente
2. La segunda versión usaba `docker exec` para parsear YAML de `ros2 topic echo`, lo cual es ineficiente
3. La solución final es un **servidor HTTP persistente dentro del contenedor** que se suscribe una sola vez y sirve los datos

---

## Cronología de intentos

### Intento 1: Suscripción a rosbridge desde el navegador (ROSLIB.js)

**Cómo funcionaba:**
```javascript
jointStatesListener = new ROSLIB.Topic({
  ros: ros,
  name: '/joint_states',
  messageType: 'sensor_msgs/JointState',
  throttle_rate: 100
});
```

**Problema:** El navegador recibía el mensaje (verificado via WebSocket test directo a `ws://localhost:9090`), pero la UI mostraba `--`. Posible causa: QoS mismatch (`/joint_states` usa `transient_local`, pero el roslib.js no lo negociaba bien, o el `throttle_rate` causaba problemas).

**Veredicto:** Funcionó a medias, difícil de debuggear sin DevTools abiertos permanentemente.

### Intento 2: docker exec + ros2 topic echo + parsear YAML

**Cómo funcionaba:**
```python
cmd = "bash -c 'source setup.bash && ros2 topic echo /joint_states --once'"
r = c.exec_run(cmd)
# parsear YAML de la salida
```

**Problemas encontrados:**
- `ros2 topic echo --field name --field position --once` → nunca termina (timeout 124)
- `ros2 topic echo --qos-durability transient_local --once` → salida vacía
- `ros2 topic echo --once` (sin flags) → salida en formato YAML, pero el parsing de listas con `- item` no funcionaba
- El contenedor `mir_ur_driver` no tenía el script `joint_reader.py` montado como volumen

**Veredicto:** Funcionó pero era lento (cada petición = `docker exec` + `ros2 init` + spin hasta recibir mensaje), y frágil ante cambios de formato.

### Intento 3 (final): Servidor HTTP persistente + proxy

**Arquitectura:**
```
[UR5e] → /joint_states (400Hz)
   ↓
[joint_server.py en mir_ur_driver :9091]  ← suscripción persistente, se inicia una vez
   ↓
[Backend mir_ui :8080/api/ur/joints]  ← proxy HTTP simple con cache 100ms
   ↓
[Navegador]  ← polling cada 200ms (5Hz en UI)
```

**Archivos creados/modificados:**

1. **`mir_suite/scripts/joint_server.py`** (nuevo) - Servidor HTTP Python en el contenedor
   - Se suscribe a `/joint_states` con QoS `VOLATILE/RELIABLE` (no necesita transient_local porque se queda conectado)
   - Cachea el último mensaje en memoria
   - Sirve JSON en `GET /joints` con la estructura:
     ```json
     {
       "names": ["right_elbow_joint", ...],
       "position": [-0.845, ...],
       "left": {"elbow_joint": 1.262, ...},
       "right": {"elbow_joint": -0.845, ...},
       "age_s": 0.05,
       "stale": false
     }
     ```
   - También expone `GET /health` para healthcheck

2. **`mir_suite/backend/main.py`** (modificado) - Endpoint más simple
   ```python
   JOINT_SERVER_URL = "http://localhost:9091/joints"

   @app.get("/api/ur/joints")
   async def ur_joints():
       # cache 100ms
       async with httpx.AsyncClient(timeout=1.0) as client:
           r = await client.get(JOINT_SERVER_URL)
           return r.json()
   ```

3. **`mir_suite/docker-compose.yml`** (modificado) - Volumen para futuros reinicios
   ```yaml
   - ./scripts/joint_server.py:/joint_server.py
   ```

4. **`mir_suite/scripts/ur_entrypoint.sh`** (modificado) - Lanza el servidor al iniciar el contenedor
   ```bash
   python3 /joint_server.py > /var/log/mir/joint_server.log 2>&1 &
   ```

5. **`mir_suite/frontend/index.html`** (modificado) - Polling REST en lugar de WebSocket
   ```javascript
   async function fetchURJoints() {
     const r = await fetch('/api/ur/joints');
     const d = await r.json();
     renderJointsFromREST(d);
   }
   setInterval(fetchURJoints, 200);
   ```

---

## Despliegue sin reiniciar el contenedor

Como el contenedor `mir_ur_driver` tenía el driver UR corriendo y conectado a los brazos, **no se podía reiniciar** (eso habría matado la conexión). Por eso se desplegó en caliente:

```bash
# 1. Copiar el script al contenedor sin reiniciar
docker cp scripts/joint_server.py mir_ur_driver:/joint_server.py
docker exec mir_ur_driver chmod +x /joint_server.py

# 2. Lanzar el servidor en background
docker exec -d mir_ur_driver bash -c "source setup.bash && python3 /joint_server.py > log 2>&1"

# 3. Verificar que responde
curl http://localhost:9091/health  # → {"ok": true}
curl http://localhost:9091/joints  # → 12 joints
```

---

## Bug del Hz parpadeante (5 ↔ 400)

**Síntoma:** El label mostraba "12 joints @ 5Hz" y luego cambiaba a "12 joints @ ~400Hz" repetidamente.

**Causa:** Había **dos** funciones JavaScript actualizando el mismo elemento `ur-joint-states`:
- `renderJoints()` (suscripción rosbridge) → ponía `@ ~400Hz`
- `renderJointsFromREST()` (polling REST) → ponía `@ 5Hz (REST)`

Como ambas se ejecutaban en momentos distintos, el texto parpadeaba entre los dos valores.

**Solución aplicada en `frontend/index.html`:**
- Estandarizar el texto a `12 joints @ 400Hz` (la frecuencia REAL de publicación del joint_state_broadcaster)
- Agregar el `(age X.XXs)` para que el usuario vea qué tan frescos son los datos
- Agregar flag `STALE` si los datos tienen más de 2 segundos sin actualizarse

```javascript
// Antes (bug):
jsEl.textContent = `${n} joints @ 5Hz (REST)`;     // REST
jsEl.textContent = `... @ ~400Hz`;                  // rosbridge

// Después (fix):
jsEl.textContent = `${n} joints @ 400Hz${staleTag} (age ${age.toFixed(2)}s)`;
```

---

## Valores de referencia de los joints

Cuando los robots están en su posición actual (verificado el 22-Jun-2026):

| Brazo | Joint | Valor (rad) | Equivalente (°) |
|---|---|---|---|
| Left | shoulder_pan | -0.020 | -1.2° |
| Left | shoulder_lift | -0.706 | -40.4° |
| Left | elbow | 1.262 | 72.3° |
| Left | wrist_1 | -3.218 | -184.3° |
| Left | wrist_2 | -1.558 | -89.3° |
| Left | wrist_3 | -3.335 | -191.1° |
| Right | shoulder_pan | 0.350 | 20.1° |
| Right | shoulder_lift | -2.621 | -150.2° |
| Right | elbow | -0.845 | -48.4° |
| Right | wrist_1 | -1.046 | -59.9° |
| Right | wrist_2 | 1.050 | 60.2° |
| Right | wrist_3 | -5.611 | -321.5° |

---

## Verificación final

```bash
# 1. Servidor vivo
curl -s http://localhost:9091/health  # → {"ok": true}

# 2. Joints correctos
curl -s http://localhost:9091/joints | python3 -m json.tool  # → 12 joints

# 3. Backend proxy
curl -s http://localhost:8080/api/ur/joints | python3 -m json.tool  # → mismo JSON

# 4. UI renderizando
# Refrescar navegador con Ctrl+Shift+R
# Ver "12 joints @ 400Hz (age 0.05s)" en el panel UR
# Ver 6 valores numéricos por brazo actualizándose 5 veces/segundo
```

---

## Lecciones aprendidas

1. **rosbridge WebSocket desde navegador es frágil**: problemas de QoS, throttle, reconexión. Para datos que se necesitan en la UI, polling REST es más predecible.

2. **`docker exec` por cada petición es caro**: cada `docker exec` spawna un proceso (~100-200ms overhead). Un servidor HTTP persistente dentro del contenedor es 10x más rápido.

3. **QoS `transient_local` vs `volatile`**: para suscripciones persistentes (servidor que se queda conectado), `volatile` es suficiente. `transient_local` se necesita cuando un cliente se conecta y quiere recibir el último valor inmediatamente.

4. **PolyScopeX no tiene dashboard server**: el `dashboard_client` siempre se sale con warning en estos robots. Para recovery, hay que ir a Polyscope directamente.

5. **Deploy sin reiniciar**: `docker cp` + `docker exec -d` permite actualizar archivos y lanzar procesos sin matar containers con servicios corriendo.

---

## Archivos del proyecto

| Archivo | Cambio |
|---|---|
| `mir_suite/scripts/joint_server.py` | Nuevo, servidor HTTP persistente |
| `mir_suite/scripts/ur_entrypoint.sh` | Modificado, lanza joint_server.py al inicio |
| `mir_suite/docker-compose.yml` | Modificado, volumen `./scripts/joint_server.py:/joint_server.py` |
| `mir_suite/backend/main.py` | Modificado, `/api/ur/joints` ahora hace proxy a `localhost:9091` |
| `mir_suite/frontend/index.html` | Modificado, polling REST en lugar de WebSocket + fix del Hz parpadeante |
| `mir_suite/docs/joints_display_fix.md` | Este documento |
