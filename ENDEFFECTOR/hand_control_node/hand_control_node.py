#!/usr/bin/env python3
"""BrainCo Revo1 hands - finger CONTROL ROS2 node (counterpart to touch_sensor_node).

Subscribes std_msgs/Int32MultiArray on:
    /left_hand/command    (slave 0x7e, e.g. /dev/ttyUSB0)
    /right_hand/command   (slave 0x7f, e.g. /dev/ttyUSB1)
Each message is 6 finger targets [thumb, thumb_aux, index, middle, ring, pinky],
0 = fully OPEN .. 1000 = fully CLOSED (thumb & thumb_aux are clamped to 500, per
BrainCo's limit). Mirrors BrainCo's revo1_ctrl.py (client.set_finger_positions).

Modes:
    --mock   Log every command + cycle a demo open/close (no hardware, no SDK).
             Great to see it working in the UI log viewer without a hand.
    (real)   Drive the hands via the official Python SDK `bc_stark_sdk` (aarch64
             wheel exists). Needs hands connected + powered; validate on hardware.

Run in a ROS2 container on ROS_DOMAIN_ID=75:
    python3 hand_control_node.py --mock
    python3 hand_control_node.py --ports /dev/ttyUSB0:left /dev/ttyUSB1:right
"""

import argparse
import threading
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import Int32MultiArray

SLAVE_ID = {"left": 0x7E, "right": 0x7F}
OPEN = [0, 0, 0, 0, 0, 0]
CLOSE = [500, 500, 1000, 1000, 1000, 1000]  # thumb/thumb_aux capped at 500


def clamp_positions(vals):
    """Coerce to 6 ints in [0,1000]; thumb + thumb auxiliary (idx 0,1) capped at 500."""
    out = []
    for i in range(6):
        v = int(vals[i]) if i < len(vals) else 0
        v = max(0, min(1000, v))
        if i < 2:
            v = min(v, 500)
        out.append(v)
    return out


class HandControlNode(Node):
    def __init__(self, mock, ports):
        super().__init__("hand_control_node")
        self.mock = mock
        self.ports = ports          # {port: side}
        self._targets = {}          # side -> [6] latest commanded
        self._dirty = {}            # side -> bool (new command pending)
        self._lock = threading.Lock()

        sides = {"left", "right"} if mock else set(ports.values())
        for side in sides:
            self.create_subscription(
                Int32MultiArray, f"/{side}_hand/command",
                lambda m, s=side: self._on_cmd(s, m), 10)

        if mock:
            self.get_logger().info("MOCK mode: logging commands + demo open/close every 3s")
            self._demo_closed = False
            self.create_timer(3.0, self._demo_tick)
        else:
            for port, side in ports.items():
                self.get_logger().info(f"REAL mode: hand '{side}' on {port}")
                threading.Thread(target=self._run_real_hand, args=(port, side), daemon=True).start()

    def _on_cmd(self, side, msg):
        pos = clamp_positions(list(msg.data))
        with self._lock:
            self._targets[side] = pos
            self._dirty[side] = True
        self.get_logger().info(f"{side} command -> {pos}")

    def _demo_tick(self):
        self._demo_closed = not self._demo_closed
        pos = CLOSE if self._demo_closed else OPEN
        for side in ("left", "right"):
            self.get_logger().info(f"[demo] {side} -> {'CLOSE' if self._demo_closed else 'OPEN'} {pos}")

    def _run_real_hand(self, port, side):
        """Apply the latest commanded target to one hand at ~20 Hz. Mirrors revo1_ctrl.py.

        NOTE: implemented against the documented bc_stark_sdk API; validate with a
        hand connected + powered.
        """
        import asyncio

        try:
            # SDK v0.7.x: the modbus/finger API lives in main_mod.stark (not main_mod).
            from bc_stark_sdk.main_mod import stark as libstark
        except Exception as e:  # pragma: no cover - depends on install
            self.get_logger().error(
                f"[{side}] bc_stark_sdk not available ({e}). Install: pip install bc_stark_sdk")
            return

        async def loop():
            # Connect like BrainCo's revo1_ctrl_dual.py: modbus_open directly at 115200,
            # device id 1 (default). One hand per port.
            slave_id = 1
            client = await libstark.modbus_open(port, libstark.Baudrate.Baud115200)
            try:
                info = await client.get_device_info(slave_id)
            except Exception as e:
                self.get_logger().error(
                    f"[{side}] hand not responding on {port} @115200 ({e}). "
                    f"Check POWER (UR tool output voltage = 24V? arms on?) and RS-485 wiring (A/B).")
                return
            self.get_logger().info(f"[{side}] {getattr(info, 'description', 'device')} connected (slave {slave_id}) ready for commands")
            await client.set_finger_positions(slave_id, OPEN)  # start open

            while rclpy.ok():
                target = None
                with self._lock:
                    if self._dirty.get(side):
                        target = self._targets.get(side)
                        self._dirty[side] = False
                if target is not None:
                    try:
                        await client.set_finger_positions(slave_id, target)
                    except Exception as e:
                        self.get_logger().error(f"[{side}] set_finger_positions failed: {e}")
                await asyncio.sleep(0.05)

            libstark.modbus_close(client)

        try:
            asyncio.run(loop())
        except Exception as e:  # pragma: no cover
            self.get_logger().error(f"[{side}] control loop stopped: {e}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mock", action="store_true", help="log commands + demo (no hardware)")
    ap.add_argument("--ports", nargs="*", default=["/dev/ttyUSB0:left", "/dev/ttyUSB1:right"],
                    help="real mode: port:side pairs, e.g. /dev/ttyUSB0:left")
    args = ap.parse_args()

    ports = {}
    for spec in args.ports:
        port, _, side = spec.partition(":")
        if side not in ("left", "right"):
            raise SystemExit(f"bad --ports entry '{spec}', expected PORT:left|right")
        ports[port] = side

    rclpy.init()
    node = HandControlNode(mock=args.mock, ports=ports)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
