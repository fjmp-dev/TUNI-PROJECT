# touch_sensor_node

**File:** `touch_sensor_node.py`

ROS2 node that publishes the BrainCo Revo1 hands' **touch sensor** data as
`ros2_stark_interfaces/TouchStatus` on:
- `/left_hand/touch_status` (slave_id 0x7e)
- `/right_hand/touch_status` (slave_id 0x7f)

Each message has 5 `TouchStatusItem` (thumb, index, middle, ring, pinky) with
normal/tangential force, direction, and proximity — matching BrainCo's `TouchFingerItem`.

## Modes
- `--mock` — synthesize a moving "press wave" (no hardware, no SDK). Used to build and
  demo the UI touch panel end-to-end.
- real (default) — read the hands via the official Python SDK **`bc_stark_sdk`**
  (`pip install bc_stark_sdk`; an **aarch64 wheel** exists → runs on the Jetson).
  Follows BrainCo's `revo1_touch.py`: auto-detect + `modbus_open` per port, enable
  the touch sensors, then loop `get_touch_sensor_status`. **Needs a hand connected +
  powered; validate on hardware.**

## Run (in a ROS2 container on ROS_DOMAIN_ID=75 with ros2_stark_interfaces sourced)
```bash
# mock (no hardware)
python3 touch_sensor_node.py --mock
# real
pip install bc_stark_sdk
python3 touch_sensor_node.py --ports /dev/ttyUSB0:left /dev/ttyUSB1:right
```
The UI (`UI/web/src/components/TouchPanel.svelte`) subscribes to these topics via
rosbridge (:9090) and renders 2 hands × 5 fingers.

## Why Python (not the C++ ros2_stark_controller)
The bundled C++ `libbc_stark_sdk.so` is x86-64 (won't run on the aarch64 Jetson), and the
old C API is deprecated on the current hand firmware. The Python SDK ships an aarch64
wheel and uses the current v2.0.2 touch API — so this node avoids the whole problem.
