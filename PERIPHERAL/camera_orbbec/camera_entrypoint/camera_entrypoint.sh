#!/bin/bash
# Camera container. The camera node is NOT auto-launched — it starts ON DEMAND
# from the UI via /api/nodes/camera_color or /api/nodes/camera_depth. Only ONE
# variant can run at a time (single USB device), so they're separate launcher nodes.
source /opt/ros/humble/setup.bash
source /root/workspace/ros_ws/install/setup.bash 2>/dev/null || true
mkdir -p /var/log/mir

echo "[camera] Container up. Camera is OFF — start 'Camera (color)' or 'Camera (color+depth)' from the UI."

# --- USB bus watchdog -------------------------------------------------------
# The Orbbec (2bc5:080b) falls off the USB bus while still physically plugged in: the
# kernel stops listing it, so the ROS node runs but never gets a frame and the UI just
# shows a black feed. Recovery is a hub power-cycle, which needs root on the HOST -- so
# this only DROPS A REQUEST (logs/ is bind-mounted); the root systemd unit
# mir-usb-reset.path performs the actual reset. The container stays unprivileged.
#
# Only fires while a camera node is actually running: nobody wants a hub cycled because
# the camera is idle and unplugged. Rate-limited to one request every 2 minutes and 3
# attempts in a row -- if three hub cycles have not brought it back, it is physical and
# a fourth will not help.
#
# It watches for BOTH failure modes, because they look identical from the UI (black feed)
# and only one of them is visible in sysfs:
#   (a) the camera vanishes from the bus  -> no 2bc5 device
#   (b) the camera is on the bus but wedged -> it enumerates, the node opens it, the
#       stream reports enabled, and no frame ever arrives. Only a hub power-cycle clears
#       this (a USBDEVFS_RESET ioctl does not). Detected here as "node running, device
#       present, yet /camera/color/image_raw/compressed has no publisher rate".
usb_watchdog() {
    local attempts=0 quiet=0
    while true; do
        sleep 20
        # Nothing to recover if no camera node is running.
        pgrep -f "[o]rbbec" >/dev/null || { attempts=0; quiet=0; continue; }

        if ! grep -qs 2bc5 /sys/bus/usb/devices/*/idVendor; then
            reason="not on the USB bus"
        elif ! timeout 8 ros2 topic hz -w 5 /camera/color/image_raw/compressed 2>/dev/null | grep -q "average rate"; then
            # Present but silent. Require two consecutive silent checks (~40 s) so a
            # camera that is merely still warming up is never yanked off its hub.
            quiet=$((quiet + 1))
            [ "$quiet" -lt 2 ] && continue
            reason="on the bus but not streaming"
        else
            attempts=0; quiet=0; continue
        fi

        quiet=0
        if [ "$attempts" -ge 3 ]; then
            continue   # give up asking; the UI still offers the manual button
        fi
        attempts=$((attempts + 1))
        echo "[camera] $reason while its node runs — requesting a hub power-cycle (attempt $attempts/3)"
        echo "force" > /var/log/mir/usb_reset.request 2>/dev/null || \
            echo "[camera] could not write the reset request (is logs/ mounted?)"
        sleep 100   # the helper needs ~15 s; wait before considering another attempt
    done
}
usb_watchdog >> /var/log/mir/camera_usb_watchdog.log 2>&1 &

trap "echo '[camera] stopped'; kill 0; exit 0" SIGTERM SIGINT
sleep infinity &
wait
