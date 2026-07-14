#!/bin/bash
# Installs the host-side USB reset helper. Run ONCE, with sudo:
#   sudo bash PERIPHERAL/camera_orbbec/usb_reset/install_host_helper.sh
#
# After this, the "Reset USB" button in the Camera tab works, and the camera container
# can request a reset by itself when the device falls off the bus.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"

[ "$(id -u)" -eq 0 ] || { echo "run with sudo"; exit 1; }

chmod +x "$DIR/usb_reset_camera.sh"
install -m 644 "$DIR/mir-usb-reset.service" /etc/systemd/system/mir-usb-reset.service
install -m 644 "$DIR/mir-usb-reset.path"    /etc/systemd/system/mir-usb-reset.path
systemctl daemon-reload
systemctl enable --now mir-usb-reset.path

echo
systemctl --no-pager --lines=0 status mir-usb-reset.path | head -3
echo
echo "Installed. The UI can now request a USB reset; only this root unit performs one."
