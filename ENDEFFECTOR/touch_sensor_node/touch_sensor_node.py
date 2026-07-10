#!/usr/bin/env python3
"""BrainCo Revo1 hands - touch sensor ROS2 node.

Publishes ros2_stark_interfaces/TouchStatus per hand:
    /left_hand/touch_status    (slave_id 0x7e, e.g. /dev/ttyUSB0)
    /right_hand/touch_status   (slave_id 0x7f, e.g. /dev/ttyUSB1)

Each TouchStatus carries 5 TouchStatusItem (thumb, index, middle, ring, pinky),
each with normal_force1..3, tangential_force1..3, tangential_direction1..3,
self_proximity1/2, mutual_proximity, status. This exactly matches the fields of
BrainCo's revo1 TouchFingerItem, so no message changes are needed.

Modes:
    --mock   Synthesize touch data (no hardware, no bc_stark_sdk needed). For UI /
             pipeline development and demos.
    (real)   Read the hands via the official Python SDK `bc_stark_sdk`
             (pip install bc_stark_sdk - an aarch64 wheel exists, so it runs on the
             Jetson). Follows BrainCo's revo1_touch.py example. Needs a hand connected
             and powered.

Run inside a ROS2 container that has ros2_stark_interfaces sourced and is on
ROS_DOMAIN_ID=75 (so the UI can see it over rosbridge):
    python3 touch_sensor_node.py --mock
    python3 touch_sensor_node.py --ports /dev/ttyUSB0:left /dev/ttyUSB1:right
"""

import argparse
import math
import threading
import time

import rclpy
from rclpy.node import Node

from ros2_stark_interfaces.msg import TouchStatus, TouchStatusItem

FINGERS = ["thumb", "index", "middle", "ring", "pinky"]
SLAVE_ID = {"left": 0x7E, "right": 0x7F}


def _make_item(normal, tangential=0, direction=0, proximity=0, status=0):
    """Build a TouchStatusItem from scalar magnitudes (0..65535)."""
    it = TouchStatusItem()
    it.normal_force1 = int(normal) & 0xFFFF
    it.normal_force2 = int(normal * 0.7) & 0xFFFF
    it.normal_force3 = int(normal * 0.4) & 0xFFFF
    it.tangential_force1 = int(tangential) & 0xFFFF
    it.tangential_force2 = int(tangential * 0.6) & 0xFFFF
    it.tangential_force3 = int(tangential * 0.3) & 0xFFFF
    it.tangential_direction1 = int(direction) & 0xFFFF
    it.tangential_direction2 = int(direction) & 0xFFFF
    it.tangential_direction3 = int(direction) & 0xFFFF
    it.self_proximity1 = int(proximity) & 0xFFFFFFFF
    it.self_proximity2 = int(proximity * 0.8) & 0xFFFFFFFF
    it.mutual_proximity = int(proximity * 0.6) & 0xFFFFFFFF
    it.status = int(status) & 0xFF
    return it


class TouchSensorNode(Node):
    def __init__(self, mock, ports, rate_hz):
        super().__init__("touch_sensor_node")
        self.pubs = {
            side: self.create_publisher(TouchStatus, f"{side}_hand/touch_status", 10)
            for side in ("left", "right")
        }
        self.rate_hz = rate_hz
        if mock:
            self.get_logger().info(
                f"MOCK mode: publishing synthetic touch for both hands at {rate_hz} Hz"
            )
            self._t0 = time.time()
            self.create_timer(1.0 / rate_hz, self._tick_mock)
        else:
            # Real hardware: one asyncio reader thread per hand/port.
            for port, side in ports.items():
                self.get_logger().info(f"REAL mode: hand '{side}' on {port}")
                threading.Thread(
                    target=self._run_real_hand, args=(port, side), daemon=True
                ).start()

    # ---------- MOCK ----------
    def _tick_mock(self):
        t = time.time() - self._t0
        for side in ("left", "right"):
            msg = TouchStatus()
            msg.slave_id = SLAVE_ID[side]
            offset = 0.0 if side == "left" else 0.9
            items = []
            for i in range(5):
                # A press "wave" sweeps across the fingers; idle stays near 0.
                phase = t * 1.2 - i * 0.7 - offset
                press = max(0.0, math.sin(phase)) ** 2  # 0..1, spends most time idle
                normal = press * 3200
                tangential = press * 900
                direction = (int(t * 40) + i * 30) % 360
                proximity = press * 55000
                items.append(_make_item(normal, tangential, direction, proximity, 0))
            msg.data = items
            self.pubs[side].publish(msg)

    # ---------- REAL (bc_stark_sdk) ----------
    def _run_real_hand(self, port, side):
        """Async reader for one hand. Mirrors BrainCo's revo1_touch.py.

        NOTE: implemented against the documented bc_stark_sdk API; validate with a
        hand connected + powered.
        """
        import asyncio

        try:
            # SDK v0.7.x: the modbus/touch API lives in main_mod.stark (not main_mod).
            from bc_stark_sdk.main_mod import stark as libstark
        except Exception as e:  # pragma: no cover - depends on install
            self.get_logger().error(
                f"[{side}] bc_stark_sdk not available ({e}). "
                f"Install with: pip install bc_stark_sdk"
            )
            return

        async def loop():
            # Connect like BrainCo's revo1_ctrl_dual.py: open Modbus DIRECTLY at 115200
            # (auto-detect is unreliable), device id 1 (the default). One hand per port.
            slave_id = 1
            client = await libstark.modbus_open(port, libstark.Baudrate.Baud115200)
            try:
                info = await client.get_device_info(slave_id)
            except Exception as e:
                self.get_logger().error(
                    f"[{side}] hand not responding on {port} @115200 ({e}). "
                    f"Check POWER (UR tool output voltage = 24V? arms on?) and RS-485 wiring (A/B).")
                return
            self.get_logger().info(f"[{side}] {getattr(info, 'description', 'device')} connected (slave {slave_id})")
            # Enable all 5 finger touch sensors (0x1F) - disabled by default on boot.
            await client.touch_sensor_setup(slave_id, 0x1F)
            await asyncio.sleep(1.0)

            period = 1.0 / self.rate_hz
            while rclpy.ok():
                fingers = await client.get_touch_sensor_status(slave_id)  # 5 items
                msg = TouchStatus()
                msg.slave_id = slave_id
                items = []
                for f in fingers[:5]:
                    it = TouchStatusItem()
                    it.normal_force1 = int(f.normal_force1) & 0xFFFF
                    it.normal_force2 = int(f.normal_force2) & 0xFFFF
                    it.normal_force3 = int(f.normal_force3) & 0xFFFF
                    it.tangential_force1 = int(f.tangential_force1) & 0xFFFF
                    it.tangential_force2 = int(f.tangential_force2) & 0xFFFF
                    it.tangential_force3 = int(f.tangential_force3) & 0xFFFF
                    it.tangential_direction1 = int(f.tangential_direction1) & 0xFFFF
                    it.tangential_direction2 = int(f.tangential_direction2) & 0xFFFF
                    it.tangential_direction3 = int(f.tangential_direction3) & 0xFFFF
                    it.self_proximity1 = int(f.self_proximity1) & 0xFFFFFFFF
                    it.self_proximity2 = int(f.self_proximity2) & 0xFFFFFFFF
                    it.mutual_proximity = int(f.mutual_proximity) & 0xFFFFFFFF
                    it.status = int(f.status) & 0xFF
                    items.append(it)
                msg.data = items
                self.pubs[side].publish(msg)
                await asyncio.sleep(period)

            libstark.modbus_close(client)

        try:
            asyncio.run(loop())
        except Exception as e:  # pragma: no cover
            self.get_logger().error(f"[{side}] reader stopped: {e}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mock", action="store_true", help="publish synthetic data (no hardware)")
    ap.add_argument(
        "--ports",
        nargs="*",
        default=["/dev/ttyUSB0:left", "/dev/ttyUSB1:right"],
        help="real mode: port:side pairs, e.g. /dev/ttyUSB0:left",
    )
    ap.add_argument("--rate", type=float, default=15.0, help="publish rate (Hz)")
    args = ap.parse_args()

    ports = {}
    for spec in args.ports:
        port, _, side = spec.partition(":")
        if side not in ("left", "right"):
            raise SystemExit(f"bad --ports entry '{spec}', expected PORT:left|right")
        ports[port] = side

    rclpy.init()
    node = TouchSensorNode(mock=args.mock, ports=ports, rate_hz=args.rate)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
