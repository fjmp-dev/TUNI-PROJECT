# MIR Suite - Agent Rules (AGENTS.md)

These rules are auto-loaded by opencode at startup. They apply to every
session working in this repo. Edit them in `mir_suite/AGENTS.md` and restart
opencode for changes to take effect.

---

## 1. Project context

This is the **MIR Suite**: a Docker-based control system for a MiR200 mobile
robot + 2 UR5e arms + Orbbec camera + Nordbo force sensors, running on a
Jetson AGX Orin ("Kevin") at 192.168.1.75.

**Hard rule:** the real workspace is at `/home/lab/Desktop/MIR/`. Inside it:
- `mir_suite/` — the actual code (docker compose, FastAPI backend, Svelte
  frontend, ROS2 node launcher). This is the git repo. EDIT HERE.
- `otros_proyectos_eemil/`, `pandai_ark/`, `pbd_system/`, etc. — original
  projects by Eemil, mounted read-only into containers but NOT in our git
  repo. **DO NOT MODIFY.** They are dependencies, not ours.

The single source of truth for project context is
**`documentation/MIR_SUITE_MANUAL.md`** (the technical manual — every fact in it
was verified against the live system), plus `SECURITY.md` for the hardening log.
Read them on first session. The old PROJECT.md and the HTML reports were deleted
on 2026-07-13 because they described a pre-refactor system (mir_raw.py, privileged
containers, the old UI); if git history resurfaces them, do not trust their facts.

---

## 2. Safety (real robots)

**Before any real-robot action, READ `mir_suite/SECURITY.md` and the
`MiR/documentation/` notes.** The project has documented:

- MiR200 errors 9000 (safety PLC + emergency stop) make the network collapse
  when the robot enters "Running" mode. Do NOT push the robot into Running
  without a technician ready to recover it.
- UR5e arms are mounted BACKWARDS on the MiR torso. Positive deltas do not
  always mean what you'd think. Verify with a small delta (≤ 0.01 rad) first.
- Wrist joints (wrist_1/2/3) should NOT be moved without explicit user OK.
- The simulated container `mir_ur_driver_sim` exists for safe testing. Use
  it for anything that could go wrong.

**Hard rule for any move command:** start with delta ≤ 0.01 rad. Confirm
the move physically happened (read /joint_states after). Only then scale up.

---

## 3. Conventions

### File paths
- Backend Python: `mir_suite/UI/backend/main.py` (single 1100-line file)
- Frontend Svelte: `mir_suite/UI/web/src/`
- Container config: `mir_suite/docker-compose.yml`
- Per-component scripts: `mir_suite/UR/`, `mir_suite/MiR/`,
  `mir_suite/PERIPHERAL/`, `mir_suite/ENDEFFECTOR/`
- Container env / secrets: `mir_suite/config/.env` (in `.gitignore`!)
- Logs: `mir_suite/logs/`

### Code style
- Python: type hints, Pydantic for request bodies, fastapi dependency
  injection where it helps, asyncio for I/O, threading for in-process locks.
  Backend uses inline `# === Section ===` headers to navigate the single file.
- Bash: `set -e` at the top of any non-trivial script; use `flock -n` when
  multiple processes can call the same script; redirect logs to
  `/var/log/mir/<script>.log`; use `tee -a $LOG` for the user-facing prefix.
- Svelte: 5 with `$state` and `$effect`. Reactive stores live in
  `lib/*.svelte.js`. No component-level state for cross-component data.
- Docs: English in code comments, Spanish in user-facing markdown (per the
  original project rules in `/home/lab/Desktop/MIR/rules.md` — note this
  file was deleted in a previous refactor; the convention still holds).

### Git
- Default branch: `main`. Previous refactor session created
  `refactor/by-component` — check with `git branch` before pushing.
- Commits: `type(scope): subject` conventional format.
- Push only what's been tested locally. The user has had multiple tokens
  revoked; push carefully.

---

## 4. Communication

- Language: Spanish with the user (matches `rules.md` original).
- Verbose logging is fine — the user is debugging, more signal is better.
- When a task touches security (auth, tokens, pkill patterns, exec_run), be
  EXTRA careful: read SECURITY.md first, validate any user input that
  reaches shell or subprocess.
- When proposing a refactor, show the diff and explain the trade-off BEFORE
  making changes. The user prefers plan-first for non-trivial work.

---

## 5. Hard "do not" list

- **DO NOT** edit files in `otros_proyectos_eemil/`, `pandai_ark/`,
  `pbd_system/`. They are mounted read-only into containers and are
  Eemil's original code.
- **DO NOT** use `git push` without checking the branch first. The user has
  a `refactor/by-component` branch from a previous session.
- **DO NOT** restart the `mir_ur_driver` container while the UR arms are
  mid-move. The driver owns the RTDE/URScript sockets; yanking it mid-trajectory
  can fault the arm controller.
- **DO NOT** add shell metacharacters (`;|&<>*$()"'` etc.) to any pattern
  that ends up in a `pkill -f`, `docker exec`, or `subprocess` call. The
  `_safe_pkill()` helper validates a whitelist; respect it.

---

*Last updated: 2026-07-08*
