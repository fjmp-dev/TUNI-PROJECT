#!/bin/bash
# Build helper for MIR Suite on Jetson AGX Orin ("Kevin").
# This kernel lacks the iptables `raw` table, so `docker compose build` fails
# with "can't initialize iptables table 'raw'". The workaround is to build with
# --network=host, which docker compose doesn't support. This script builds each
# image individually with the right flag, then tells compose to use them.
#
# Usage:
#   ./build.sh              # build all images
#   ./build.sh mir_ui       # build only mir_ui
#   ./build.sh mir-camera   # build only camera
set -e
cd "$(dirname "$0")"

BUILDER="docker build --network=host"

# Map: compose service name -> (image tag, dockerfile path, build context)
declare -A IMAGES=(
    ["mir_ui"]="mir_ui:latest UI/ui_image/Dockerfile ."
    ["mir-camera"]="mir-camera:latest PERIPHERAL/camera_orbbec/camera_image/Dockerfile ."
    ["mir-mir"]="mir-mir:latest MiR/mir_image/Dockerfile ."
    ["mir-ur-driver"]="mir-ur-driver:latest UR/ur_driver_image/Dockerfile ."
    ["mir-mdns"]="mir-mdns:latest UI/mdns/Dockerfile ."
)

build_one() {
    local svc="$1"
    if [[ -z "${IMAGES[$svc]}" ]]; then
        echo "unknown service: $svc"
        echo "known services: ${!IMAGES[@]}"
        exit 1
    fi
    read -r tag dockerfile context <<< "${IMAGES[$svc]}"
    echo "==> building $svc -> $tag"
    $BUILDER -f "$dockerfile" -t "$tag" "$context"
}

if [[ $# -eq 0 ]]; then
    # Build everything in dependency order (base images first if any)
    for svc in mir-mdns mir_ui mir-camera mir-mir mir-ur-driver; do
        build_one "$svc"
    done
    echo ""
    echo "All images built. Now run: docker compose --profile <profile> up -d"
else
    for svc in "$@"; do
        build_one "$svc"
    done
fi
