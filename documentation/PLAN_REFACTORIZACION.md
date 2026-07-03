# Refactoring plan — status and continuation

_Last updated: 2026-07-02_

Restructuring of `mir_suite` **by robot component** (inspired by the reference repo
`waeltut/fortis-uc1-tau`), plus network cleanup (router/SIM/WiFi) and the MiR bridge.

---

## ✅ DONE (validated)

### Structure by component
- Root: `.devcontainer/`, `README.md`, `docker-compose.yml`, `base_image/`, `config/`.
- Component folders (UPPERCASE): `UR/ MiR/ BATTERY_MS/ ROUTER_MODEM/ HEAD_NECK/ PERIPHERAL/ ENDEFFECTOR/ UI/`, each with `documentation/`.
- **Each file/script in its own subfolder with a README** (UR/joint_server/, MiR/bridge_mir/, PERIPHERAL/camera_orbbec/…).
- Global `documentation/` (PROJECT.md, reports, `referencias/` with manuals/notes/screenshots).

### Self-contained ROS workspace
- `robot_workspace/` (formerly `eemils_work/pbd_system`, a copy of `/home/lab/pbd_system`, ~5 GB, **gitignored**). Eemil's original untouched.
- `docker-compose.yml` mounts `./robot_workspace` (relative paths, 4 services).
- **`ros_ws/src/` reorganized by component**: `UR_arms/ end_effector/ peripherals/ shared_common/ _archives/` (colcon discovers them recursively; 548 `install/` symlinks retargeted → no rebuild needed).

### Infra / network (resolved)
- **Teltonika RUTX50 router** (`192.168.1.1`): factory reset → `admin / Fastlab2026`. Elisa SIM: **Connected, 5G**, APN Auto (weak signal RSRP −128, improve antennas).
- **MiR WiFi**: 2.4 GHz `RUT_D571_2G` (key `g9K2JeHu`), **DHCP reservation → always `.13`**, **0% packet loss** (was 20-100%). Chronic issue resolved.
- **MiR bridge** (`mir_mir`): the rosbridge was wedging from reconnect churn → fixed + **exponential backoff** in the entrypoint. `/odom`, battery, 89 topics in ROS2. Stable.

### Others
- `mir-camera / mir-mir / mir_ui` images rebuilt with the new paths (use `docker build --network=host`).
- Sim validated (`Simulation ready`, joint_server 200, UI 200, 129 topics).
- Parent folder cleaned (`otros_proyectos_eemil/`, `documentation/referencias/`).
- Removed the duplicate root `backend/` (kept `UI/backend/`).

---

## 🔜 PENDING — continuation

### A. Close the software refactoring
1. **Git**: set the user's identity **locally** in the repo (currently it is Eemil's):
   `git config user.name "<your name>"; git config user.email "<your email>"`.
   Then commit the reorg (103 files: 88 D of old paths + new ones). Suggested: branch `refactor/by-component`.
2. **Clean workspace rebuild**: add `COLCON_IGNORE` in
   `robot_workspace/ros_ws/src/shared_common/cartesian_controllers/cartesian_controller_simulation/`
   (needs MuJoCo, not available and not used) and run `rm -rf build && colcon build --symlink-install --base-paths src` inside a `--network host` container. Verify everything compiles (the 16 we tested already compiled OK).
3. **Old docs**: `PROJECT.md`, `docs`, `reports` still cite `/home/lab/pbd_system` (text only, no runtime impact) → update to `robot_workspace`.
4. **`.devcontainer`**: validate by opening it in VS Code (it is a template).
5. **UI**: write the proper UI documentation that was requested (how it was built, config) in `UI/documentation/`.
6. **Finish the docs → English translation** (deferred until the project is marked fully complete).
   Already in English: all component READMEs, root README, this plan, router `hallazgos`,
   `rosbridge_diagnosis`, `BATTERY_MS`, `.devcontainer`, `mir_diagnostico`, `comandos.txt`,
   `EXTERNAL_PROJECTS`, and **all code comments** (scripts, main.py, .gitignore).
   **Still to translate (when the project is complete):** `PROJECT.md` (766 lines, describes the
   OLD structure), `MiR/documentation/mir_integration.md`, `mir_connectivity_issue.md`,
   `UR/documentation/joints_display_fix.md`, `AVANCE_JUNTA.md`, `ARCHIVOS_IMPORTANTES.txt`,
   the 12 HTML reports under `documentation/reports/`, and the personal notes under
   `documentation/referencias/`.

### B. Investigations by component (phase 2)
| Component | What to investigate |
|---|---|
| **BATTERY_MS** | MiR battery ✅ (`/MC/battery_percentage`, ~54%). Missing: the UPPER-part battery (torso/Jetson/UR) — any telemetry? Check hardware. |
| **HEAD_NECK** | Neck motor that rotates the head: which controller? does it publish/receive over ROS or serial? |
| **ENDEFFECTOR** | Inventory of end effectors (BrainCo hand in `src/end_effector/`), how they are controlled, topics/services. |
| **PERIPHERAL** | `microphones/` and `speakers/`: what hardware and how it is captured/played. |
| **ROUTER_MODEM** | Improve mobile signal (antennas/placement); document the final SIM config. |

### C. MiR (operation)
- **Error 911** (3D floor camera, `REMOVING_CAMERA`): clear it in the MiR UI or via REST (`clear_error_state`); if it persists, reboot the MiR and check the camera cable. It is internal to the MiR, not the suite.
- The bridge backoff takes effect on the next `mir_mir` restart.

### D. Real-hardware validation
- Everything was validated in the **`sim`** profile. Still to test with the **real arms** (`arms` profile) following the sim-first rule, when the user authorizes.
- Operational reminder: shut down with `docker compose ... down` (not `docker rm -f`), and if DDS discovery fails, clean `fastrtps_*` from `/dev/shm`.

---

## References
- Router/SIM: `ROUTER_MODEM/documentation/hallazgos.md`
- MiR bridge: `MiR/documentation/rosbridge_diagnosis.md`
- Battery: `BATTERY_MS/documentation/README.md`
- ROS packages by component: `robot_workspace/ros_ws/src/*/README.md`
