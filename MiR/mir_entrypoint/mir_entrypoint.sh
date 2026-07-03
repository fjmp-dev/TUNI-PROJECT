#!/bin/bash
source /opt/ros/humble/setup.bash
source /root/workspace/ros_ws/install/setup.bash 2>/dev/null || true

echo "[mir] Starting MiR200 ROS1->ROS2 bridge..."

HEARTBEAT="${MIR_BRIDGE_HEARTBEAT:-/tmp/mir_bridge_last_io}"
export MIR_BRIDGE_HEARTBEAT="$HEARTBEAT"
touch "$HEARTBEAT"   # grace window before the first /odom arrives

# Liveness node: touches the heartbeat on every real /odom message coming through
# the bridge -- a true end-to-end signal. Replaces the old stdout heuristic, which
# never fired during healthy operation (the bridge's own log lines were filtered
# out, so a healthy bridge looked "mute" and got killed on a timer).
echo "[mir] liveness probe on ${MIR_LIVENESS_TOPIC:-/odom}"
python3 -u /mir_liveness.py 2>&1 | sed -u 's/^/[liveness] /' &
LIVENESS_PID=$!

# Watchdog: restarts the bridge when the heartbeat goes stale.
WATCHDOG_INTERVAL=${MIR_WATCHDOG_INTERVAL:-15}
echo "[mir] watchdog: every ${WATCHDOG_INTERVAL}s, mute threshold ${MIR_WATCHDOG_THRESHOLD:-25}s"
( while true; do
    sleep "$WATCHDOG_INTERVAL"
    bash /mir_watchdog.sh || true
done ) &
WATCHDOG_PID=$!

trap "kill $WATCHDOG_PID $LIVENESS_PID 2>/dev/null" EXIT

STARTED_FILE="${MIR_BRIDGE_STARTED:-/tmp/mir_bridge_started}"
export MIR_BRIDGE_STARTED="$STARTED_FILE"

# Reconnect with exponential backoff. A fixed fast retry hammers the MiR's
# rosbridge (Tornado) with half-open connections and can WEDGE it, so repeated
# quick failures back off (10 -> 20 -> 40 -> 60s cap). A connection that stayed
# up a healthy while resets the backoff.
BACKOFF_MIN=${MIR_BACKOFF_MIN:-10}
BACKOFF_MAX=${MIR_BACKOFF_MAX:-60}
BACKOFF=$BACKOFF_MIN
while true; do
    echo "[mir] Connecting to MiR200 rosbridge at 192.168.1.13:9090..."
    # Mark each (re)launch so the watchdog can grant a startup grace window:
    # mir_raw.py spends ~25-30s discovering topic types before it republishes
    # anything, so /odom (the liveness signal) is silent during that time.
    date +%s > "$STARTED_FILE"
    _start=$(date +%s)
    python3 -u /mir_raw.py 2>&1
    _ran=$(( $(date +%s) - _start ))
    if [ "$_ran" -ge 60 ]; then
        BACKOFF=$BACKOFF_MIN
    else
        BACKOFF=$(( BACKOFF * 2 )); [ "$BACKOFF" -gt "$BACKOFF_MAX" ] && BACKOFF=$BACKOFF_MAX
    fi
    echo "[mir] Bridge exited after ${_ran}s. Retrying in ${BACKOFF}s..."
    sleep "$BACKOFF"
done
