#!/bin/bash
# Watchdog for the MiR ROS1->ROS2 bridge (mir_raw.py).
#
# Health signal: the heartbeat file refreshed by mir_liveness.py on every /odom
# message. /odom flows ~3.5 Hz even while the MiR is in Pause, so a stale
# heartbeat means the bridge is "alive but mute" -> restart it. We must not
# modify Eemil's mir_raw.py, so we only kill it; the entrypoint relaunches.
#
# Before restarting, probe the MiR's own rosbridge to log WHERE the hang is:
#   - MiR rosbridge answers       -> our client died; restarting fixes it.
#   - MiR rosbridge unresponsive  -> MiR-side hang; restart likely won't help,
#     so we log it loudly (the MiR itself may need a restart).

BRIDGE_PID=$(pgrep -f "[m]ir_raw.py" | head -1)
[ -z "$BRIDGE_PID" ] && exit 0   # not running; the entrypoint will (re)start it

NOW=$(date +%s)

# Startup grace: mir_raw.py spends ~25-30s discovering topic types before it
# republishes anything, so /odom is silent during startup. Don't judge a freshly
# (re)launched bridge as mute until it has had time to finish discovery -- killing
# it mid-discovery is exactly the churn that wedges the MiR's own rosbridge.
STARTED_FILE="${MIR_BRIDGE_STARTED:-/tmp/mir_bridge_started}"
STARTUP_GRACE="${MIR_WATCHDOG_STARTUP_GRACE:-60}"
STARTED=$(cat "$STARTED_FILE" 2>/dev/null || echo 0)
[ "$((NOW - STARTED))" -lt "$STARTUP_GRACE" ] && exit 0   # still starting up

HEARTBEAT="${MIR_BRIDGE_HEARTBEAT:-/tmp/mir_bridge_last_io}"
THRESHOLD="${MIR_WATCHDOG_THRESHOLD:-25}"   # /odom ~3.5Hz; 25s mute => dead
LAST=$(stat -c %Y "$HEARTBEAT" 2>/dev/null || echo 0)
AGE=$((NOW - LAST))

[ "$AGE" -le "$THRESHOLD" ] && exit 0   # healthy: fresh /odom data is flowing

# Mute. Classify the failure by probing the MiR rosbridge directly. Retry a few
# times: a single probe is too sensitive over the marginal -87 dBm WiFi link, so
# we only call it "unresponsive" if EVERY attempt fails.
if python3 - <<'PY'
import base64, os, socket, sys, time
def probe():
    try:
        s = socket.create_connection(("192.168.1.13", 9090), timeout=4)
        key = base64.b64encode(os.urandom(16)).decode()
        s.sendall((f"GET / HTTP/1.1\r\nHost: 192.168.1.13\r\nUpgrade: websocket\r\n"
                   f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
                   f"Sec-WebSocket-Version: 13\r\n\r\n").encode())
        ok = b"101" in s.recv(1024)
        s.close()
        return ok
    except Exception:
        return False
for attempt in range(3):
    if probe():
        sys.exit(0)        # MiR rosbridge answered -> it's healthy
    time.sleep(1)
sys.exit(1)                # all attempts failed -> genuinely unresponsive
PY
then
    WHERE="our client died (MiR rosbridge OK) -- restart should fix it"
else
    WHERE="MiR-side rosbridge unresponsive -- restart may not help; MiR may need a reboot"
fi

echo "[watchdog] $(date -Iseconds) bridge MUTE for ${AGE}s (>${THRESHOLD}s): ${WHERE}; killing client PID ${BRIDGE_PID}"
kill -9 "$BRIDGE_PID" 2>/dev/null
# Reset the heartbeat to "now" so the relaunched bridge gets a full grace window
# (THRESHOLD seconds) to reconnect and resume /odom before being judged again.
touch "$HEARTBEAT"
exit 0
