# MIR BOT Project Rules

**Project:** Dockerizing R&D tools for MIR + Universal Robots (MIC-733 / "Kevin")
**Location:** Lab, Finland
**Status:** Active Development

---

## 1. Safety First (Physical & Digital)

1. **MiR200 Base:** ALWAYS OFF unless explicitly authorized. Battery safety range: 20-80%.
2. **UR5e Arms:** NO sudden movements. Always verify teach pendants are in correct mode before any driver activation.
3. **Isolation:** NEVER modify, delete, or overwrite files in the original project folders: `pandai_ark/`, `pbd_system/`, `teleop/`, `ur_ws/`, `aiprism_ws/`, etc. All our work must live in isolated directories.
4. **Backups:** If a script must touch an existing folder, create a `.bak` copy first.

---

## 2. Development Philosophy

- **No shortcuts.** The simplest path is not the preferred path if it sacrifices robustness, safety, or maintainability.
- **Documentation is mandatory.** Every step, discovery, and configuration change must be recorded in `memory.md`.
- **Web-first.** The UI must be accessible via browser (localhost / network IP) without requiring local ROS/Docker installation on user laptops.
- **Docker-native.** All new tools must be containerized to avoid dependency hell on the host (Kevin).

---

## 3. Architecture Rules

- **UI Container:** Runs on Kevin. Users access via `http://<kevin_ip>:<port>`.
- **Backend Container:** The existing `pbd_system` or `teleop` container remains untouched. We may bridge to it via ROS 2 networking or run a new container that inherits from the same base image.
- **Network Segments:**
  - `195.148.48.186` (lan1) → University/Internet access (SSH, Browser UI).
  - `192.168.1.75` (lan3) → Robot internal network (UR5e, MiR, sensors).
- **No Physical SIM yet:** The physical SIM for the router switch is deferred to a later phase.

---

## 4. Communication

- **MIR BOT persona:** Patient, structured, safety-focused, encouraging.
- **Language:** Spanish (as requested by user).
- **All system-reminders must be obeyed.** If a reminder conflicts with a request, the reminder takes precedence.

---

*Last updated: 2026-06-08*
*Author: MIR BOT*
