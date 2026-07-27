#!/bin/bash
# Desktop launcher for the MIR Suite: lets you turn the stack on or off.
#
# "Start" brings up the always-on stack (caddy, mdns, UI, camera, MiR
# bridge) and opens the UI in the browser. It does NOT touch the UR arms
# driver (profiles "arms"/"sim") -- that stays a deliberate, separate action
# started from inside the UI (node launcher -> ur_start.sh), so arms never
# move on their own just because someone opened this suite.
#
# "Stop" stops everything, including the arms driver container if it
# happens to be up (--profile arms --profile sim makes it visible to
# `docker compose stop` too, which otherwise ignores profile-gated services).
set -e
cd "$(dirname "$0")"

URL="https://mir-suite.local"
FALLBACK_URL="https://localhost"
ALL_PROFILES=(--profile arms --profile sim --profile full)

open_browser() {
    if command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$1" >/dev/null 2>&1 &
    elif command -v firefox >/dev/null 2>&1; then
        firefox "$1" >/dev/null 2>&1 &
    else
        chromium "$1" >/dev/null 2>&1 &
    fi
    disown
}

start_suite() {
    echo "==> Starting the MIR Suite..."
    docker compose up -d

    echo "==> Waiting for the UI to answer..."
    ready=0
    for i in $(seq 1 30); do
        if curl -ks -o /dev/null -m 2 "$URL"; then
            ready=1
            break
        fi
        sleep 1
    done

    if [ "$ready" -ne 1 ]; then
        echo "==> $URL did not answer, trying $FALLBACK_URL..."
        URL="$FALLBACK_URL"
        for i in $(seq 1 15); do
            if curl -ks -o /dev/null -m 2 "$URL"; then
                ready=1
                break
            fi
            sleep 1
        done
    fi

    if [ "$ready" -ne 1 ]; then
        echo "==> ERROR: the UI never answered. Check with: docker compose ps"
        read -p "Press Enter to close..."
        exit 1
    fi

    echo "==> Opening $URL"
    open_browser "$URL"

    echo ""
    echo "Done. If no window opened, go to: $URL"
    sleep 5
}

stop_suite() {
    echo "==> Stopping the MIR Suite (including the UR arms driver, if it was up)..."
    docker compose "${ALL_PROFILES[@]}" stop
    echo ""
    echo "Done. Everything is stopped."
    sleep 3
}

clear
echo "========================================"
echo "           MIR SUITE - Jetson"
echo "========================================"
echo "  1) Start the Suite (dockers + UI)"
echo "  2) Stop the Suite"
echo "========================================"
read -p "Choose an option [1/2]: " choice

case "$choice" in
    1) start_suite ;;
    2) stop_suite ;;
    *)
        echo "Invalid option."
        sleep 2
        exit 1
        ;;
esac
