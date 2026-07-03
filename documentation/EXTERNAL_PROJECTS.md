# Referenced external projects

These folders exist on the Jetson (Kevin) but are **not versioned** because they are
original third-party projects. The project rule is not to modify them. After the
reorg they were moved into `/home/lab/Desktop/MIR/otros_proyectos_eemil/`.

| Folder | Description |
|---|---|
| `pbd_system/` | Programming by Demonstration (PBD) system. Contains `ros_ws` with `duo_ur`, `moveit_utils_pkg`, UR driver, MoveIt config, etc. |
| `pandai_ark/` | Pandai Ark stack (perception, navigation, Jetson). |
| `Universal_Robots_ROS2_Driver/` | Universal Robots ROS2 driver source. |

## Use in this project

`mir_suite` used to mount Eemil's `pbd_system` workspace directly. Since the reorg it
uses its **own self-contained copy** under `robot_workspace/` (gitignored), mounted
relatively in `docker-compose.yml`:

```yaml
volumes:
  - ./robot_workspace:/root/workspace
```

That gives access to `duo_ur`, `moveit_utils_pkg` and the rest of the packages
(now reorganized under `robot_workspace/ros_ws/src/` by component) without touching
the originals.
