# MiR200 diagnosis — 2026-06-29

> Note: several "pending" items below were later RESOLVED (WiFi moved to 2.4 GHz,
> 0% loss; rosbridge wedge fixed) — see `rosbridge_diagnosis.md` and the router
> `../../ROUTER_MODEM/documentation/hallazgos.md`. Kept as the original dated diagnosis.

Deep-dive session on the MiR200 (`MiR_S455`) to understand its instability.
Summary: **the MiR is healthy; the underlying problem is the WiFi signal**, and along
the way a bug in the bridge watchdog was fixed.

---

## 1. MiR access (how to diagnose)

- **REST API:** `http://<ip>/api/v2.0.0` — authentication
  `Authorization: Basic base64(user:sha256_hex(password))`.
- **Credentials:** `admin` / `admin` (work).
- `/api/v2.0.0/status` is **public** (no auth); the rest requires auth.
- Open ports: 80, 443, 8080, **9090 (rosbridge)**, 22 (SSH).
- Useful endpoints seen: `/status`, `/system/info`, `/metrics`, `/registers`,
  `/settings`, `/settings/advanced`, `/maps`, `/missions`, `/wifi/connections`.

Auth header generator (bash):
```bash
H="Authorization: Basic $(printf 'admin:%s' \
   "$(printf admin | sha256sum | cut -d' ' -f1)" | base64 -w0)"
curl -s -H "$H" http://192.168.1.13/api/v2.0.0/system/info
```

---

## 2. Health status (all OK except the WiFi)

| Area | Value | Verdict |
|---|---|---|
| MiR software | **2.13.3.2**, MIR200 model, NUC PC (BIOS 2017) | Old but stable |
| Active errors | `errors: []`, `mir_robot_errors 0` | 🟢 Clean (the ~9000 before were historical) |
| Battery | ~85% (~11 h remaining) | 🟢 |
| Localization | `localization_score 0.28` (0 = perfect) | 🟢 |
| rosbridge :9090 | Alive, answers services | 🟢 (when there is network) |
| **WiFi signal** | **−86 to −88 dBm** on 5 GHz | 🔴 **Root cause #1** |
| Clock | **Feb 2016** (~10 years off) | 🟡 NTP not syncing |

---

## 3. Root cause #1 — marginal WiFi (5 GHz, −87 dBm)

- The MiR connects over WiFi (adapter `wlp2s0`) to the SSID **`RUT_D572_5G`**
  (Teltonika, 5 GHz band). Measured RSSI: **−86/−87/−88 dBm** = very weak.
- 5 GHz has much less range/penetration than 2.4 GHz → at that distance the link
  is right at the edge.
- **Observed LIVE during the session:** the MiR **dropped off the network
  entirely** (`ARP FAILED`, REST `HTTP 000`) and **did not re-associate on its own for +70 s**.
  That is the instability happening in real time.
- The documented symptom "the MiR rosbridge hangs frequently" is largely explained
  by this: when the WiFi degrades, `roslibpy` gives `RosTimeoutError: Failed to
  connect to ROS`, and when it drops entirely, even the raw WebSocket handshake
  fails to connect (`No route to host`).
- When the link is good, everything works: 25/25 REST probes OK at 6–21 ms,
  15/15 WS handshakes OK at 4–9 ms, and the bridge republishes `/odom` at ~3–4 Hz.

**Underlying fix:** move the MiR to **2.4 GHz** (same Teltonika network, better range)
or improve AP coverage. 2.4 GHz at the same distance usually gives ~10–15 dB better
(from −87 to ~−73, already usable).

### Blocker at the time (pending action with Wael)
- In the MiR network list **only `RUT_D572_5G` appears** (no 2.4 GHz SSID visible),
  and **we don't have the password** for the Teltonika network.
- **QUESTION FOR WAEL:** can the **2.4 GHz** SSID on the Teltonika (`RUT_D572`) be
  enabled and/or the WiFi **password** shared, so the MiR can connect to 2.4 GHz?
  (2.4 and 5 GHz usually share the password.)

### Important about the network (do not use dd-wrt)
- The host **Kevin** is wired to the **Teltonika** (`192.168.1.75`, ifaces
  `lan2`/`lan4`). It is **not** on the `dd-wrt` network (`192.168.12.x`).
- If the MiR connects to dd-wrt it gets a `192.168.12.x` IP that **Kevin does not
  route** (it sends it out to the internet) → **the suite can't see it**.
- Rule: **the MiR must be on the same network as Kevin → the Teltonika
  `192.168.1.x`** (ideally its 2.4 GHz SSID). Expected IP: `192.168.1.13`.

---

## 4. Own bug found and fixed — bridge watchdog

### The problem
The old watchdog (`mir_watchdog.sh`) measured "activity" by reading the **stdout**
of `mir_raw.py`. But the node is named `rosbridge_explorer`, so **all** of its log
lines contain `[rosbridge_explorer]:` — and the `entrypoint` **excluded exactly those
lines** from refreshing the heartbeat. Result:

- In normal operation **nothing** refreshed the timestamp → after 90 s the watchdog
  thought it was "mute" and **killed a healthy bridge**.
- Each forced restart generated **connection churn** to the MiR rosbridge, which
  contributes to hanging it. The "safety" watchdog **caused** part of the
  instability it was meant to prevent.

### The fix (without touching Eemil's `mir_raw.py`)
1. **`scripts/mir_liveness.py`** (new): ROS2 node that subscribes to `/odom`
   (publishes ~3.5 Hz even in Pause) and refreshes the heartbeat
   `/tmp/mir_bridge_last_io` with **real data** from the full MiR→bridge→ROS2 path.
   It only subscribes; it never commands the robot.
2. **`scripts/mir_watchdog.sh`** (rewritten):
   - **Startup grace window** (`MIR_WATCHDOG_STARTUP_GRACE`, 60 s):
     `mir_raw.py` takes ~25–30 s to discover topic types before republishing
     anything, so a freshly-launched bridge is not judged "mute".
   - **Mute threshold** (`MIR_WATCHDOG_THRESHOLD`, 25 s) on the heartbeat.
   - **Probe with 3 retries** to the MiR rosbridge to distinguish whether the hang
     is the **MiR** or **our client** (a single attempt gave false negatives due to
     the marginal WiFi).
3. **`scripts/mir_entrypoint.sh`** (rewritten): launches the liveness node, marks
   each bridge (re)start for the grace window, and removes the broken touch-by-stdout.
4. **`docker-compose.yml` / `docker/mir/Dockerfile`**: the two new files
   (`mir_watchdog.sh`, `mir_liveness.py`) are mounted/copied.

### Validated live
- Startup: the bridge survives discovery (not killed during grace), `/odom` starts
  flowing (~45 s) and the heartbeat stays fresh (<1 s).
- Stable state: **0 kills** by the watchdog with a healthy bridge.
- Real recovery: **freezing** the bridge (`SIGSTOP`, simulating "alive but mute"),
  the watchdog detected it (MUTE 40 s) and restarted it on its own. ✅

### Environment variables (tunable)
| Var | Default | What it does |
|---|---|---|
| `MIR_WATCHDOG_STARTUP_GRACE` | 60 | Grace after bridge (re)start (s) |
| `MIR_WATCHDOG_THRESHOLD` | 25 | `/odom` muteness to declare a hang (s) |
| `MIR_WATCHDOG_INTERVAL` | 15 | How often the watchdog runs (s) |
| `MIR_LIVENESS_TOPIC` | `/odom` | Topic used as the liveness signal |

---

## 5. Other minor findings

- **Clock in 2016:** the MiR system date is ~10 years behind (NTP not syncing).
  Cosmetic, but it pollutes log timestamps and validations. Pending: point it to an
  NTP (the Teltonika) or set it.
- **`/metrics` is minimal** in software 2.13 (only battery, uptime, errors, WiFi,
  position); it does not expose CPU/temperature/motors.
- The "logs" under `/software/logs` are just the **firmware update history**
  (2.1.0 → … → 2.13.3.2), not error logs.

---

## 6. Status and next steps

| Task | Status |
|---|---|
| Bridge resilience (watchdog/liveness) | ✅ **Done and validated** |
| WiFi → 2.4 GHz | ✅ Resolved 2026-07-02 (was blocked on the SSID/password) |
| Fix the MiR clock/NTP | ⏳ Pending |
| Re-enable MiR telemetry in the UI (`/robot_pose`, `/scan`, `/odom`) | ⏳ Pending (depends on a stable network) |

**Immediate action (at the time):** ask **Wael** whether we can (a) enable the
Teltonika 2.4 GHz SSID `RUT_D572` and (b) have the WiFi password, to move the MiR to
2.4 GHz on the `192.168.1.x` network (where Kevin lives).
