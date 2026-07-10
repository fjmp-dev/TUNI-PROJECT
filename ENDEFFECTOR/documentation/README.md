# ENDEFFECTOR — documentation

## What the end effectors are
Two **BrainCo "Stark"/Revo dexterous hands** (灵巧手), one per arm, with **capacitive
touch sensors** (tactile version). Controlled by `ros2_stark_controller` (in
`robot_workspace/ros_ws/src/shared_common/demos/`) over **serial** (`/dev/ttyUSB0`,
`/dev/ttyUSB1` = two FTDI FT231X), Modbus, baud **460800**, `slave_id 0x7e`=left / `0x7f`=right.
Description/MoveIt in `robot_workspace/ros_ws/src/end_effector/` (`BrainCoRightHandURDF`,
`_duo_ur_ee_moveit_config`). Messages in `ros2_stark_interfaces`.

## Goal
Add to the UI a live view of the hands' **touch sensor** (per-finger force/pressure).
Data path: `stark_node` publishes `touch_status` → rosbridge :9090 → UI (Svelte + roslib).
`ros2_stark_interfaces` (the msgs) build fine; only the controller node is blocked.

## The SDK situation (2026-07-03, investigated in depth)
- The bundled `libbc_stark_sdk.so` in the repo is **x86-64** → cannot build/run on the
  aarch64 Jetson.
- BrainCo's aarch64 SDK exists: `https://app.brainco.cn/universal/bc-stark-sdk/libs/v2.0.2/linux-arm64.zip`
  (v2.0.2, reachable from the Jetson). It contains `dist/shared/linux/libbc_stark_sdk.so`
  (ARM aarch64) + `dist/include/stark-sdk.h`.
- ⚠️ **The API CHANGED**: v2.0.2 uses a NEW API (`stark_get_touch_status` → `CTouchFingerData`,
  `array_pressure_touch_buffer_*`, `device_info_uses_revo2_touch_api`, ...). Our
  `stark_node.cpp` uses the OLD `modbus_get_touch_status` API — **incompatible**.
- ⚠️ Our old lib's strings show the old touch functions are **"deprecated for current
  firmware, return empty"** → even an old-version aarch64 lib would likely return no touch
  data with the hands' current firmware. **We must use the v2.0.2 API.**

## Plan
1. **Unblock the driver (aarch64 + v2.0.2 API):** either
   - (a) **Use BrainCo's official current ROS2 driver/examples** for v2.0.2 (preferred if it
     exists and is maintained — see BrainCoTech/brainco-hand-sdk + Revo2 ROS integration guides), or
   - (b) **Port our `ros2_stark_controller`** to the v2.0.2 API (new header `stark-sdk.h` +
     aarch64 `.so`): rewrite `stark_node.cpp` (open device, `stark_get_touch_status`, publish),
     detect Revo1 vs Revo2 via device_info, and update `ros2_stark_interfaces/TouchStatus` to
     the new per-finger data shape.
2. **Test** with a hand connected (FTDI serial) + powered → confirm `touch_status` publishes.
3. **UI panel:** subscribe to `touch_status` (both hands) over rosbridge, render 2 hands × 5
   fingers with per-finger force/pressure (e.g., hand outline + per-finger heatmap/bars).

## Blockers/needs
- A hand connected + powered to the Jetson to test the driver.
- Decide (a) official driver vs (b) port the custom one.
- (Downloaded SDK is in scratch; to use it, bring the v2.0.2 aarch64 lib + header into `ros2_stark_controller/`.)
