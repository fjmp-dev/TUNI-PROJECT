# MIR Suite - Security Hardening (Session 22-Jun-2026)

## Overview

Six critical security issues were identified during a hardcoded-value audit and fixed in this session. Each fix is defense-in-depth — multiple layers, not a single chokepoint.

---

## 1. Seed passwords moved to environment variables

**Problem:** The `wael/wael` and `pablo/pablo` passwords were hardcoded in `_seed_profiles()`. Anyone with repo access had the production credentials.

**Fix in `UI/backend/main.py`:**
- `WAEL_PASS` and `PABLO_PASS` env vars (default to the old values for back-compat).
- `_log_default_passwords()` runs at boot and `logging.warning()`s if any seed still uses its factory password.

**Fix in `config/.env`:**
- `WAEL_PASS=wael`, `PABLO_PASS=pablo` (overridable).
- Comment block at the top: "WARNING: defaults are factory passwords. The backend logs a warning at boot if any of these are unchanged — override before production deployment."

---

## 2. UR container autodetection removed (now env-driven)

**Problem:** `_ur_container_name()` had a hardcoded priority (`("mir_ur_driver", "mir_ur_driver_sim")`) and a fallback that preferred the real container over the sim. If both were running (testing), the real always won. `MIR_SERVICES` didn't list the sim, so it was invisible in the UI.

**Fix:**
- Each UR container declares its own identity via the `UR_CONTAINER` env var (set in `docker-compose.yml` per-service).
- Backend: `UR_CONTAINER = os.environ.get("UR_CONTAINER", "mir_ur_driver")` — used verbatim, no autodetection, no priority. Predictable and explicit.
- `MIR_SERVICES` now includes `mir_ur_driver_sim` with label "UR5e Driver (sim)".

**Files:** `UI/backend/main.py`, `docker-compose.yml`.

---

## 3. pkill patterns are whitelist-validated

**Problem:** `pkill -f '{pattern}'` in `_node_stop` and freedrive-disable used the pattern from the NODES dict. Today those are dev-written, but any future code that interpolates external data into a pkill pattern could escalate to arbitrary shell execution (e.g. `; rm -rf /`).

**Fix in `UI/backend/main.py`:**
- New `_safe_pkill(container, pattern)` helper validates `pattern` against `^[A-Za-z0-9_./ -]+$` (no shell metacharacters).
- On unsafe pattern: `logging.error()` and `raise ValueError()`.
- `_node_stop` now calls `_safe_pkill()`; freedrive-disable uses `_safe_pkill_in()` (fire-and-forget).
- All current NODES patterns pass the validator (verified: `touch_sensor_node.py --ports`, `hand_control_node.py --ports`, `ros2 bag record`, `orbbec`).

---

## 4. Auth tokens have TTL and hourly cleanup

**Problem:** `_tokens` grew without bound, never expired. A stolen token had unlimited access. With long-running backends, the dict accumulated stale entries.

**Fix in `UI/backend/main.py`:**
- `TOKEN_TTL = int(os.getenv("TOKEN_TTL", "86400"))` (24h default).
- `_issue_token()` now records `expires = time.time() + TOKEN_TTL`.
- `_resolve_token()` lazily evicts expired tokens on access (returns None, never re-evicts on retry storms).
- New `_token_cleanup_task()` background coroutine: every hour, sweeps `_tokens` and drops everything expired. Wired up in the `@app.on_event("startup")` hook alongside the Nordbo readers.
- `TOKEN_TTL=86400` added to `config/.env` with comment.

**Operational note:** A restart of `mir_ui` already logs everyone out (in-memory dict, no persistence). The TTL is belt-and-suspenders for long-running deployments that survive weeks.

---

## 5. Per-node locks (Python) + flock (bash) — defense in depth

**Problem:** `_node_start` had a TOCTOU race: two concurrent clicks (or two overlapping apply-my-nodes calls) both saw "not running" in the pgrep check, both spawned the process, and ended up with two of them. `_ur_container_name` had a similar issue from SSH/manual invocation racing the backend.

**Fix — Layer 1 (Python):**
- New `_node_locks: dict[str, threading.Lock]` (one lock per node-id).
- `_get_node_lock(node_id)` lazily creates the lock.
- `_node_start` and `_node_stop` now wrap their bodies in `with _get_node_lock(node_id):` and delegate to `_node_start_locked` / `_node_stop_locked`. The lock is held only for the duration of pgrep + exec_run (a few hundred ms at most). Unrelated nodes don't serialize.

**Fix — Layer 2 (bash):**
- `UR/ur_start/ur_start.sh` opens FD 200 to `/tmp/ur_driver.lock` and `flock -n` (non-blocking). If another `ur_start.sh` is already in the critical section, exits 0 immediately.
- `trap "flock -u $LOCKFD" EXIT` releases the lock when the script exits.
- This protects against SSH'd-in manual invocations racing the backend, which the Python lock can't reach.

**Why both:** Python lock = UI thread safety. Bash lock = cross-process safety. A failure in one doesn't open a hole in the other.

---

## 6. applyNodes only on explicit login (not on reload)

**Problem:** `auth.svelte.js` had a comment saying "Auto-start this profile's saved nodes (only on explicit login, not on reload)" — but the design relied entirely on the developer remembering not to call `applyNodes()` from `App.svelte`'s token-restore effect. Nothing prevented a future change from regressing this.

**Fix in `UI/web/src/lib/auth.svelte.js`:**
- Added `_applied_this_session` module-level flag (false on init, true after first `login()` call, reset to false on `logout()`).
- `applyNodes()` is now gated by `if (!_applied_this_session)`. Even if `login()` were called twice (user mashes the button), nodes only start once.
- The flag is **defense in depth** — the primary invariant is still "App.svelte never calls applyNodes on token-restore". But if that invariant is ever broken in the future, the flag limits the blast radius to one apply per session.

**Verification:** The architecture is already correct — `App.svelte` only calls `api.me()` (profile hydration), never `applyNodes()`. `Sidebar.svelte` has a manual "Start my nodes" button for explicit user retries. The fix makes the invariant harder to break.

---

## Pending tickets (alto/medio)

These are NOT fixed in this session but tracked here so they don't get lost.

### Ticket 1: Rate limiting on /api/login
- Lockout of 5 attempts/min per IP.
- In-memory tracker keyed on client IP.
- Currently `_verify_password` is unbounded — a brute-force attack has no rate limit.

### Ticket 2: CORS headers
- No CORS currently configured (FastAPI default is no CORS).
- Needed if the UI is served from a different origin than the backend (e.g. reverse proxy, dev server on different port).

### Ticket 3: WebSocket Terminal exec_resize validation
- `api.exec_resize(exec_id, height=int(ev["rows"]), width=int(ev["cols"]))` accepts any int.
- A malicious admin could send `rows=99999999, cols=0` and crash the docker daemon.
- Add validation: positive integers, bounded (e.g. max 200×200).

### Ticket 4: pgrep pattern `[d]uo_ur_real` trick
- The `[d]uo_ur_real` pattern is a shell trick to avoid matching the pgrep command itself.
- Not a bug, but should be documented (most devs don't know this idiom).

### Ticket 5: Hardcoded `/dev/ttyUSB0:left /dev/ttyUSB1:right`
- If the BrainCo hands get plugged into different USB ports on reboot, the touch/hand nodes won't start.
- Fix: udev rules for `/dev/brainco-left` / `/dev/brainco-right` symbolic links.

### Ticket 6: `out_task.cancel()` race in WebSocket terminal
- `asyncio.to_thread(raw.recv, ...)` may be blocked in I/O when `cancel()` is called.
- The `raw.close()` releases the socket, which unblocks recv, but bytes could leak.
- Add `await out_task` with timeout before closing the socket.

### Ticket 7: `/tmp/ur_driver.pid` orphan file
- ur_start.sh writes this but ur_stop.sh never reads it (uses pgrep instead).
- The file accumulates `</tmp>/ur_driver.pid` over container restarts.
- Cosmetic, but could be cleaned.

### Ticket 8: `if docker_client is None:` scattered ~19 times
- Centralize as a decorator `_require_docker()` that returns 503 once.
- Currently each endpoint has its own `if docker_client is None: raise HTTPException(503, ...)`.

### Ticket 9: MiR cache UI indicator
- `_mir_cache` returns `stale: true` with `age_s: 20` (the TTL), but the UI doesn't show a visual indicator when `age_s > 30`.
- Add a "stale" badge in the MiR panel.

### Ticket 10: `UR_JOINTS_TTL` not in `config/.env`
- Currently default in code (0.1 = 100ms).
- Should be overridable via env for tuning in production.

### Ticket 11: `MIR_CACHE_TTL` not in `config/.env` (it IS, but undocumented)
- It's in `.env` but no comment explaining trade-offs.
- Add comment block.

### Ticket 12: `_token_cleanup_task` error swallowing
- Currently logs and continues. On persistent errors the task dies silently.
- Add restart-on-failure logic or surface the error to a healthcheck endpoint.

### Ticket 13: `nordbo_reader` auto-reconnect never gives up
- `while True: try ... except ... await asyncio.sleep(3)` — forever.
- If a sensor is physically dead, logs flood with errors.
- Add exponential backoff cap (e.g. 60s max between retries).

### Ticket 14: `UR_FAKE_HARDWARE` typo acceptance
- `if [ "${UR_FAKE_HARDWARE:-false}" = "true" ]` — only "true" triggers. "True" or "1" don't.
- Document or normalize.

### Ticket 15: `_node_start` doesn't verify exit code of exec_run
- After `c.exec_run(["bash", "-c", full], detach=True)` returns, the script may have already failed.
- For long-running nodes, the user only sees "not running" on next status check.
- Add a small delay + re-check that the process is actually alive.

### Ticket 16: `ApplyNodes` endpoint swallows individual node errors
- `errors.append({"node": node_id, "error": str(e)})` collects errors but the response status is "ok" even if all nodes failed.
- Should return 207 (Multi-Status) or 200 with `all_started: bool` so the UI can show a partial-failure warning.

---

## Verification checklist

For each fix above, here's how to verify it's working in the lab:

1. **Seed passwords:** `docker logs mir_ui 2>&1 | grep -i "default seed password"` should show the warning at boot (since `.env` still has the defaults).
2. **UR container env:** `docker exec mir_ur_driver printenv UR_CONTAINER` should print `mir_ur_driver`. Same for the sim.
3. **pkill validation:** Try `/api/nodes/foo/stop` (a non-existent node) — should 404. The validation is internal; the public API doesn't expose it. To test directly: add a temporary test node with `pattern="; touch /tmp/pwned"` to NODES and try starting/stopping it. Should refuse with 500 + "unsafe pkill pattern" in logs.
4. **Token TTL:** Issue a token, set `TOKEN_TTL=5`, wait 6s, hit any protected endpoint — should 401.
5. **Per-node lock:** Click "Start ur_driver" twice rapidly. The second call should exit 0 immediately (idempotent) without spawning a second process. Check `docker exec mir_ur_driver pgrep -f "duo_ur_real" | wc -l` — should be 1.
6. **applyNodes flag:** Login with a profile that has 2 nodes saved. Reload the page (F5). Check that the nodes are NOT restarted (look at their log timestamps). Then click logout, login again — nodes should restart.

---

## TLS: private CA instead of a bare self-signed cert (13-Jul-2026)

**Problem:** the suite was served over HTTPS with a single self-signed certificate,
so every browser showed a full-page "Your connection is not private / attackers may
be trying to steal your information" interstitial. Users click through such warnings
by habit — which is exactly the habit that makes a real MITM on the lab LAN work.
The cert's name (`tunisuite.local`) also never resolved: the Jetson's avahi publishes
`lab.local`, so in practice everyone browsed the raw IP.

**Fix:**
- `config/tls/gen_cert.sh` now builds a **two-tier PKI**: a root CA
  (`MIR Suite Local CA`, 10 y, `ca.key` chmod 600 and gitignored) that signs a server
  cert (`suite.crt`, 825 d). Devices trust the *root*, so the server cert can be
  reissued (new IP/name/expiry) without touching any laptop or phone again.
- SANs: `mir-suite.local`, `tunisuite.local`, `lab.local`, `localhost`,
  `192.168.1.75`, `127.0.0.1` — name **or** IP both validate.
- New `mdns` service (`UI/mdns/`) publishes **`mir-suite.local`** on the LAN through
  the host's avahi over D-Bus, so the URL is a name that matches the certificate.
  It needs `-R` (no reverse record): avahi already owns the PTR for `.75` via
  `lab.local`, and re-claiming it is a name collision that kills the publisher.
- Caddy serves the public root at **`https://mir-suite.local/ca.crt`** with
  `Content-Type: application/x-x509-ca-cert` so phones offer to install it directly.
  Only the *certificate* is exposed; `ca.key` never leaves the Jetson.

**Install the CA once per device** (this is what removes the warning). On the Jetson
(or any Linux box) just run **`config/tls/trust_ca.sh`** — it finds every store and
writes to all of them.

The trap it exists to avoid: **browsers on Linux ignore the system trust store.**
Firefox and Chrome each keep their own NSS database, and the *snap* builds keep theirs
in a private path (`~/snap/chromium/current/.pki/nssdb`). Installing the CA into
`~/.pki/nssdb` or into `/usr/local/share/ca-certificates` fixes `curl` and changes
*nothing* in a snap Chromium — it still shows `ERR_CERT_AUTHORITY_INVALID`. Always
restart the browser fully afterwards: NSS is read once at startup.

Manually, per platform:
- **Linux (curl/python only):** `sudo cp ca.crt /usr/local/share/ca-certificates/mir-suite-ca.crt && sudo update-ca-certificates`
- **Firefox** (has its own store): Settings → Privacy & Security → Certificates →
  View Certificates → Authorities → Import → tick *Trust to identify websites*.
- **Windows:** double-click → Install Certificate → Local Machine → place in
  *Trusted Root Certification Authorities*.
- **Android:** browse to `/ca.crt` → Settings → Security → Install from storage → CA cert.
- **iOS/macOS:** install the profile, then *enable full trust* in
  Settings → General → About → Certificate Trust Settings (iOS skips this step at your peril).

**Verify:** `curl --cacert config/tls/ca.crt https://mir-suite.local/` must return
200 with `ssl_verify_result 0` — no `-k` anywhere.

**Not fixed / accepted:** the root CA is a real trust anchor. Anyone who steals
`ca.key` can mint certs for *any* site those devices visit, not just this suite.
It stays on the Jetson at mode 600, is excluded by `.gitignore` (`*.key`), and must
never be copied to a shared drive. Only install it on machines that actually operate
the robot.

---

*Last updated: 2026-07-13*
*Session owner: Kevin (estudiante) + opencode*
