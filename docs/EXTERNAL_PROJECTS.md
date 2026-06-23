# Proyectos externos referenciados

Estas carpetas existen en `/home/lab/Desktop/MIR` en el Jetson (Kevin) pero **no se versionan** porque son proyectos originales de terceros. La regla del proyecto es no modificarlos.

| Carpeta | Descripción |
|---|---|
| `pbd_system/` | Programming by Demonstration (PBD) system. Contiene `ros_ws` con `duo_ur`, `moveit_utils_pkg`, driver UR, config MoveIt, etc. |
| `pandai_ark/` | Pandai Ark stack (percepción, navegación, Jetson). |
| `teleop/` | Stack de teleoperación. |
| `ur_ws/` | Workspace de Universal Robots. |
| `aiprism_ws/` | Workspace de Aiprism. |

## Uso en este proyecto

`mir_suite` se apoya en el workspace de `pbd_system` montándolo dentro del contenedor `mir_ur_driver` vía `docker-compose.yml`:

```yaml
volumes:
  - /home/lab/pbd_system:/root/workspace
```

De esta forma obtenemos acceso a `duo_ur`, `moveit_utils_pkg` y demás paquetes sin copiarlos ni modificarlos.
