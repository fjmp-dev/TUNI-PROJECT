# BATTERY_MS — documentation

## MiR base battery — HAS telemetry ✅
Via the MiR bridge (rosbridge → ROS2), available in ROS2 (domain 75):
- **`/MC/battery_percentage`** — e.g. `54.13` %
- **`/MC/battery_voltage`**

Also via the MiR REST: `GET http://192.168.1.13/api/v2.0.0/status` includes
`battery_percentage`, `battery_time_remaining`, etc.

## Upper-part battery (torso/arms/Jetson) — NO telemetry found (2026-07-03)
Investigated from the Jetson (Kevin). There is **no battery telemetry** exposed to it:
- `/sys/class/power_supply/` is **empty** → the kernel monitors no battery.
- CAN buses **down/stopped** (`can0`, `can1`) → no active BMS on CAN.
- The two serial ports `/dev/ttyUSB0` and `/dev/ttyUSB1` are the **BrainCo "Stark"
  hands** (end effectors), controlled by `ros2_stark_controller` (Modbus, baud 460800,
  slave_id 0x7e=left / 0x7f=right) — **not** a BMS.
- The only power-related data on the Jetson is its own **INA3221** sensors
  (`/sys/class/hwmon/hwmon2,3`): module rails ~12 V + current draw. That is power
  **consumption**, not battery state-of-charge.

### Two likely scenarios (confirm physically — cannot be determined from software)
- **(A)** The upper part is powered from the **MiR battery** (24/48 V aux output) →
  then `/MC/battery_percentage` already covers the whole robot, and there is no
  separate "upper battery".
- **(B)** There is a **separate battery/pack** up top, but its BMS is **not wired** to
  the Jetson (no CAN, no serial) → it reports nothing. To read it, its comms interface
  (CAN/RS485/USB) would need to be connected and identified.

### Recommendation
- For the UI: show the **MiR battery** (already easy via REST/ROS). Optionally show the
  **Jetson power draw** (INA3221) as a "system power" indicator (consumption, not SOC).
- Physical check needed: is there a separate upper battery pack? Does its BMS have an
  unconnected comms port (CAN/RS485/USB)? Only then can real upper-SOC be exposed.
