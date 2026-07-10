# HEAD_NECK — documentation

## Finding (2026-07-03): the neck motor is NOT integrated into software/ROS
A full search of the project (mir_suite + robot_workspace) found **nothing** driving a
neck/head:
- **No neck/head/pan/tilt joint** in any URDF/xacro. (The `duo_ur5e_torso_moveit_config`
  "torso" only has the UR arms' `left/right_shoulder_lift_joint` — no neck joint.)
- **No motor-controller driver** anywhere (dynamixel, roboteq, odrive, feetech, stepper,
  servo, u2d2, maxon...).
- **No dedicated hardware** visible to the Jetson: the only serial devices are the two
  FTDI adapters = the BrainCo hands; CAN buses are down; no servo/motor USB device.

So the neck motor that rotates the head **exists physically but is not connected to or
controlled by the Jetson/ROS.** It is likely a standalone motor with its own controller,
or currently unused/unwired.

## To integrate it (phase 2 — needs physical inspection)
1. Physically identify the neck **motor** (brand/type: stepper, DC, servo, Dynamixel?)
   and its **controller/driver board** up in the neck/head.
2. Find its **interface**: serial (RS232/485/TTL), CAN, USB, PWM, or a proprietary box.
3. Trace where its cable goes (to the Jetson? to a separate controller? nowhere?).
4. Then write a small ROS2 driver/node to command it (and, if it reports position,
   publish it).

**Next step is on the hardware side** — there is nothing in the current software to reuse.
