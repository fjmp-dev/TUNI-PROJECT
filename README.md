# mir_suite

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
