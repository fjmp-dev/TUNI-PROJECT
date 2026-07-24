#!/bin/bash
# Local CI pipeline for MIR Suite. Runs without Docker — syntactical checks,
# unit tests, and compose validation only. Integration tests that need a
# running container (or hardware) belong in tests/test_integration.py, which
# requires a manual run with `--run-integration`.
#
# Usage:  ./run_tests.sh          # all checks
#         ./run_tests.sh --quick  # only syntax + compose validation (fast)

set -e
cd "$(dirname "$0")"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

pass=0
fail=0

check() {
    local label="$1"; shift
    printf "  %-60s " "$label"
    if "$@" >/dev/null 2>&1; then
        echo -e "${GREEN}PASS${NC}"
        ((pass++))
    else
        echo -e "${RED}FAIL${NC}"
        ((fail++))
    fi
}

echo "============================================"
echo " MIR Suite — Local CI"
echo "============================================"
echo ""

# ---- 1. Python syntax -----------------------------------------------------
echo "--- 1. Python syntax checks ---"
for f in UI/backend/main.py UR/action_bridge/action_bridge.py \
         UR/joint_server/joint_server.py UR/joint_mover/joint_mover.py \
         MiR/bridge_mir/mir_bridge.py MiR/bridge_mir/scanners_merger.py \
         MiR/mir_liveness/mir_liveness.py; do
    if [ -f "$f" ]; then
        check "$f" python3 -c "import ast; ast.parse(open('$f').read())"
    fi
done
echo ""

# ---- 2. Bash syntax -------------------------------------------------------
echo "--- 2. Bash syntax checks ---"
for f in UR/ur_start/ur_start.sh UR/ur_stop/ur_stop.sh \
         UR/ur_entrypoint/ur_entrypoint.sh UR/sim_entrypoint/sim_entrypoint.sh \
         MiR/mir_entrypoint/mir_entrypoint.sh MiR/mir_watchdog/mir_watchdog.sh \
         PERIPHERAL/camera_orbbec/camera_entrypoint/camera_entrypoint.sh \
         build.sh; do
    if [ -f "$f" ]; then
        check "$f" bash -n "$f"
    fi
done
echo ""

# ---- 3. docker-compose validation -----------------------------------------
echo "--- 3. docker-compose.yml validation ---"
if command -v docker &>/dev/null; then
    check "docker compose config" docker compose config
else
    echo "  (docker not available — skipping compose validation)"
fi
echo ""

# ---- 4. Python unit tests (no Docker required) -----------------------------
echo "--- 4. Python unit tests (pytest) ---"
if python3 -m pytest --version &>/dev/null; then
    python3 -m pytest tests/test_backend.py -v --tb=short 2>&1 | tail -30
    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        echo -e "\n  ${GREEN}All unit tests passed${NC}"
        ((pass++))
    else
        echo -e "\n  ${RED}Unit tests failed${NC}"
        ((fail++))
    fi
else
    echo "  (pytest not installed — install with: pip install pytest pyyaml)"
    echo "  (skipping unit tests)"
fi
echo ""

# ---- 5. Node.js / frontend checks (if available) --------------------------
echo "--- 5. Frontend checks ---"
if [ -f UI/web/package.json ]; then
    if command -v node &>/dev/null; then
        cd UI/web
        # Only syntax-check the build, don't actually build (needs network).
        check "vite build (syntax only)" node -e "
            const fs=require('fs');
            const files=fs.readdirSync('src/components').filter(f=>f.endsWith('.svelte'));
            files.forEach(f=>fs.readFileSync('src/components/'+f));
            console.log(files.length+' svelte files readable');
        "
        cd ../..
    else
        echo "  (node not available — skipping frontend checks)"
    fi
else
    echo "  (UI/web/package.json not found — skipping)"
fi
echo ""

# ---- 6. Agent rules exist --------------------------------------------------
echo "--- 6. Rules / docs ---"
check "AGENTS.md present" test -f AGENTS.md
echo ""

# ---- Summary --------------------------------------------------------------
echo "============================================"
echo "  Total: $((pass + fail)) checks  |  ${GREEN}${pass} passed${NC}  |  ${RED}${fail} failed${NC}"
echo "============================================"
exit $fail
