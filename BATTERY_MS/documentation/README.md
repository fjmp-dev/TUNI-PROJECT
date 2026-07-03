# BATTERY_MS — documentation

## Finding (2026-07-02): the MiR battery DOES send telemetry
Via the MiR bridge (rosbridge → ROS2), available in ROS2 (domain 75):
- **`/MC/battery_percentage`** — e.g. `54.13` %
- **`/MC/battery_voltage`**

Also via the MiR REST: `GET http://192.168.1.13/api/v2.0.0/status` includes
`battery_percentage`, `battery_time_remaining`, etc.

## Pending
- UPPER-part battery (torso/arms/Jetson PC), NOT the MiR's: investigate whether the
  Jetson/UR expose the state of their own power supply (it may have no ROS telemetry;
  check the hardware).
- Define what to show in the UI (the MiR's is easy, it comes over REST).
