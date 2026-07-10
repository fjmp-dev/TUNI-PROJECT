# bridge_mir — selective MiR <-> ROS 2 bridge

**Files:** `mir_bridge.py`, `scanners_merger.py`, `topic_config.yaml`

Adopted from Wael's `fortis-uc1-tau` repo (folder TK32, package `mir_driver`) on
2026-07-10, replacing Eemil's `mir_raw.py` (which republished EVERY MiR topic and
overloaded the shared DDS domain).

- **`mir_bridge.py`** — connects to the MiR's rosbridge (host from env `MIR_IP`)
  and bridges ONLY the topics listed in `topic_config.yaml`:
  - MiR -> ROS 2: `/f_scan`, `/b_scan`, `/odom`, `/tf`, `/tf_static`,
    `/MC/battery_percentage`
  - ROS 2 -> MiR: `/cmd_vel` (direct velocity control of the base)
  - The MiR's `map->odom` transform is filtered out so a local SLAM can own
    localization (phase 2: SLAM Toolbox + Nav2, see TK32's `slam_config`).
- **`scanners_merger.py`** — fuses the front/back SICK scans into one 360°
  `/scan` in `base_footprint` (what SLAM consumes).
- **`topic_config.yaml`** — the bridge whitelist. Keep it minimal.

Local adaptations vs upstream: `MIR_IP` env instead of a hardcoded IP, plain
bind-mounted config file (no ament share), custom `MirState` msg dropped (the UI
reads robot state via the MiR REST API), non-zero exit on connect failure so the
entrypoint's backoff loop drives reconnection, and a throttled TF-wait warning.

Launched by `MiR/mir_entrypoint/mir_entrypoint.sh` (merger once + bridge inside
the backoff loop, with the /odom liveness + watchdog unchanged).
