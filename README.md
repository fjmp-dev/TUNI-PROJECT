# MIR Suite

Control software for the FAST Lab (Tampere University) dual-arm mobile manipulator:
MiR200 base, 2 × UR5e arms, BrainCo Revo1 hands, Orbbec Gemini 335Lg camera and
Nordbo force/torque sensors, on an NVIDIA Jetson AGX Orin. Each subsystem runs in
its own Docker container and the robot is operated from a web interface with
login and role-based permissions.

Developed by **Francisco Javier Martínez Peña** (Universidad Autónoma del Estado de
México) during a research stay at the FAST Lab, June–July 2026, under the
supervision of Prof. José Luis Martínez Lastra.

## Documentation

- [Project report](documentation/PROJECT_REPORT.pdf): what was done, results, validation, limitations, open items.
- [Technical documentation](documentation/TECHNICAL_DOCUMENTATION.pdf): the reference for operating and maintaining the suite.
- [Documentation index](documentation/README.md) and a README in every component folder.

## Status (release v1.0, July 2026)

Working and used in the lab, with known limitations that matter for safety and
security. Read section 6 of the project report before relying on the system. In
particular:

- the ROS 2 (DDS) graph is reachable from the robot network without authentication;
- the software emergency stop does not currently cancel arm motions — use the hardware emergency stops;
- credentials were committed to this repository before v1.0 and remain in its history — they must be changed on the devices.

## Quick start (on the Jetson)

```bash
cp config/env.example config/.env   # then set strong passwords
docker compose --profile arms up -d # all services; the arm DRIVER is started from the UI
# or, without hardware:
docker compose --profile sim up -d  # never run arms and sim together
```

Open `https://mir-suite.local` (lab CA required) or `http://192.168.1.75`.
Tests: `./run_tests.sh`.

## Authorship note

Commits from 15 to 29 June 2026 appear under the git identity "EemilR" because
they were made from the lab workstation, which had that identity configured. They
are part of this project. Eemil Rintala's original control software (`pbd_system`,
`pandai_ark`) is not part of this repository and is not modified by it.

---

## Repository structure

Robot control system (MiR200 + 2 UR5e arms + camera + peripherals), organized
**by robot component**. Each part lives in its own folder and, inside,
**each file/script has its own subfolder with its README**.

## Structure

```
mir_suite/
├── .devcontainer/        Open the repo inside a container (VS Code)
├── docker-compose.yml    Orchestration of all containers
├── base_image/           ros2humble_dev_base base image
├── config/               .env (settings/secrets) + poses
├── UR/                   UR5e arms (driver, sim, joint server/mover, meshes, patched launch)
├── MiR/                  MiR200 (ROS1->ROS2 bridge, watchdog, liveness, image)
├── PERIPHERAL/           Peripherals, each in its own folder
│   ├── camera_orbbec/    Orbbec Gemini 335Lg camera
│   ├── microphones/      (to investigate)
│   └── speakers/         (to investigate)
├── BATTERY_MS/           Battery / BMS (to investigate)
├── ROUTER_MODEM/         Teltonika RUTX50 router / SIM (to investigate)
├── HEAD_NECK/            Neck motor (to investigate)
├── ENDEFFECTOR/          End effectors (to investigate)
├── UI/                   Web (Svelte) + backend (FastAPI) + image
├── documentation/        Cross-cutting documentation (PROJECT.md, reports)
└── robot_workspace/      ROS2 workspace (self-contained copy, not versioned)
    └── ros_ws/src/       ROS packages by component:
        ├── UR_arms/        UR5e arms driver + control + moveit
        ├── end_effector/   BrainCo hand + end-effector moveit
        ├── peripherals/    Orbbec camera, sensing, tracking
        └── shared_common/  msgs (interfaces_pkg), pcl and shared libs
```

Each component folder has its own `documentation/`.

## Getting started

```bash
# Simulation (arms in fake hardware — recommended for testing)
docker compose --profile sim up -d

# Real hardware (arms)
docker compose --profile arms up -d
```

The arms, the MiR and the camera share `ROS_DOMAIN_ID=75`. To see topics:

```bash
docker exec -it mir_ur_driver_sim bash
source /opt/ros/humble/setup.bash
ros2 topic list
```

> Note: the suite is **self-contained** — it mounts its own copy under `robot_workspace/`,
> it does not depend on `/home/lab/pbd_system` (Eemil's original stays untouched).
