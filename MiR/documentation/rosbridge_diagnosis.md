# Diagnosis: the MiR rosbridge "wedges" (2026-07-02)

## Symptom
The `mir_mir` container (bridge `mir_raw.py`) could not connect:
`roslibpy.core.RosTimeoutError: Failed to connect to ROS`, and the WebSocket handshake
to `192.168.1.13:9090` **timed out** (TCP connects but the upgrade never completes),
both from the container and **directly from the Jetson** → it was neither the network nor the code.

## Root cause
The MiR rosbridge (a **Tornado** server) **wedges** when hammered with
reconnections/half-open sockets. Vicious cycle:
1. Bad WiFi → the bridge doesn't receive `/odom` in time.
2. `mir_entrypoint.sh` had a **watchdog every 15s** (restarts if `/odom` mute >25s)
   + **retry every 10s** → they hammered the rosbridge.
3. That connection churn wedges the Tornado server → more timeouts → worse.

## Solution (verified)
1. **Fix the WiFi** (2.4 GHz, 0% loss — see [[mir-wifi-root-cause]]).
2. **Break the churn:** `docker stop mir_mir`, wait ~20s for the rosbridge to clear,
   then start again. A clean handshake returned `101 Switching Protocols` and the bridge
   connected on the first try, discovering ~150 topics and republishing into ROS2.
3. **Hardening:** added **exponential backoff** to the entrypoint retry
   (10→20→40→60s; resets if the bridge ran healthy ≥60s) so it can't wedge it again.

## Healthy state (reference)
- WS handshake to :9090 → `HTTP/1.1 101 Switching Protocols` in ms.
- `/odom` flowing (heartbeat `/tmp/mir_bridge_last_io` touched ~0s ago), `/MC/battery_percentage`
  publishing (~54%), 89 topics in ROS2 (domain 75), 0 "Bridge exited".
- If it wedges again: stop the churn and let the rosbridge breathe (do not hammer it).
