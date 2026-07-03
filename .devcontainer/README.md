# .devcontainer

Configuration to open **the whole repo inside a container** from VS Code
(the *Dev Containers* extension), like the reference repo `fortis-uc1-tau`.

## What it does
- `devcontainer.json` — on *"Reopen in Container"*, VS Code builds the image from
  `Dockerfile` and mounts the repo at `/workspace`, with host networking, `/dev` and
  `ROS_DOMAIN_ID=75` (to see the same topics as the suite).
- `Dockerfile` — based on `ros2humble_dev_base:latest` (see `../base_image/`).

## How to use it
1. Install in VS Code: *Dev Containers* (+ *Remote - SSH* if working against the Orin).
2. Open the `mir_suite` folder in VS Code.
3. F1 → **Dev Containers: Reopen in Container**.
4. You land inside with ROS2 Humble ready; source the workspace with:
   `source /opt/ros/humble/setup.bash`

> Starter template: still to be validated by opening it in VS Code (requires the base
> image to exist). Adjust with Wael according to how they work (SSH to the Orin, etc.).
