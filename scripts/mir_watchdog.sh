#!/bin/bash
# Watchdog para el bridge mir_raw.py
# Detecta cuando el bridge está "vivo pero sin datos" y lo reinicia.
# Requisito: la regla de no modificar originales -> NO tocamos mir_raw.py,
# solo lo matamos y dejamos que el entrypoint lo relance.

BRIDGE_PID=$(pgrep -f "python3 /mir_raw.py" | head -1)
[ -z "$BRIDGE_PID" ] && exit 0

# Última línea escrita en stdout del proceso
# /proc/<pid>/fd/1 -> stdout. Si no se puede leer, asumimos que está colgado.
LAST_IO_FILE="/tmp/mir_bridge_last_io"
NOW=$(date +%s)
LAST_IO=$(stat -c %Y "$LAST_IO_FILE" 2>/dev/null || echo 0)
AGE=$((NOW - LAST_IO))

# Si el bridge no escribe nada en stdout por más del umbral, lo matamos
# (env-overridable: MIR_WATCHDOG_THRESHOLD, default 90s).
THRESHOLD=${MIR_WATCHDOG_THRESHOLD:-90}
if [ "$AGE" -gt "$THRESHOLD" ]; then
    echo "[watchdog] $(date -Iseconds) bridge sin actividad por ${AGE}s (umbral ${THRESHOLD}s), reiniciando (PID $BRIDGE_PID)..."
    kill -9 "$BRIDGE_PID" 2>/dev/null
    rm -f "$LAST_IO_FILE"
    exit 0
fi
