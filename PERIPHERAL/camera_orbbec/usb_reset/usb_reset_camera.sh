#!/bin/bash
# Power-cycle the USB 3 hubs so the Orbbec Gemini 335Lg (2bc5:080b) re-enumerates.
#
# WHY THIS EXISTS: the camera drops off the USB bus while still physically plugged in
# -- the kernel lists no 2bc5 device and there is no /dev/video*, so the ROS node
# starts, loads the driver and then waits forever for hardware that is not there.
# De-authorizing and re-authorizing its hub forces the port to drop and re-detect it.
# Confirmed to recover the camera on 2026-07-14.
#
# ONLY BUS 2 (USB 3) IS TOUCHED, ON PURPOSE. The camera sits at 2-2.3, under hub 2-2.
# Bus 1 carries the keyboard, the mouse and -- critically -- BOTH FTDI adapters for the
# BrainCo hands (1-2.3.3, 1-2.3.4). Power-cycling bus 1 would yank the hands off the
# bus mid-operation, so this script must never do it automatically. Use --all only by
# hand, knowing the hands and keyboard will drop.
#
# Needs root (writes /sys/.../authorized). Run:
#   sudo bash usb_reset_camera.sh          # safe: USB3 hubs only
#   sudo bash usb_reset_camera.sh --all    # also bus 1 -- DROPS THE HANDS AND KEYBOARD
set -u

REQ="/home/lab/Desktop/MIR/mir_suite/logs/usb_reset.request"
HUBS="2-2 2-3"
FORCE=0

# TWO FAULT MODES, not one:
#   (a) the camera vanishes from the bus  -> no 2bc5 in sysfs
#   (b) the camera is ON the bus but wedged -> it enumerates, the node opens it, the
#       stream is "enabled" and then not a single frame ever arrives (seen after a hot
#       stop/start of the node). A USBDEVFS_RESET ioctl does NOT clear this; only cutting
#       the hub's power does.
# The first version of this script refused to act in case (b) ("already on the bus,
# nothing to do"), which is exactly when someone is staring at a black feed. `force`
# covers it: the caller (the UI button, or the operator) states that the camera is
# present but useless, and we cycle the hub anyway.
[ "${1:-}" = "--force" ] && FORCE=1
[ -f "$REQ" ] && grep -qs force "$REQ" && FORCE=1
if [ "${1:-}" = "--all" ]; then
    HUBS="2-2 2-3 1-2 1-3 1-4"
    FORCE=1
    echo "!! --all: bus 1 included -- the hands (FTDI) and the keyboard WILL drop"
fi

present() { grep -qs 2bc5 /sys/bus/usb/devices/*/idVendor; }

if present && [ "$FORCE" -eq 0 ]; then
    echo "camera already on the bus; nothing to do"
    exit 0
fi
if present; then
    echo "camera is on the bus but not streaming -- forcing a hub power-cycle"
else
    echo "camera (2bc5) not on the bus -- cycling hubs: $HUBS"
fi

for h in $HUBS; do
    p="/sys/bus/usb/devices/$h/authorized"
    [ -w "$p" ] || { echo "  skip $h (not writable / not present)"; continue; }
    echo "  cycling hub $h"
    echo 0 > "$p"; sleep 2
    echo 1 > "$p"; sleep 1
done

echo "  waiting for re-enumeration..."
for _ in $(seq 1 10); do
    sleep 1
    present && break
done

if present; then
    echo "OK: camera is back on the bus"
    exit 0
fi
echo "FAILED: camera still missing. This is physical now -- unplug the camera's USB"
echo "cable and plug it back in, ideally straight into a USB 3 port on the Jetson."
exit 1
