#!/usr/bin/env python3
"""Liveness probe for the MiR ROS1->ROS2 bridge.

Subscribes to a topic the MiR publishes continuously even while in Pause
(/odom, ~3.5 Hz) and touches a heartbeat file on every message received. The
watchdog reads that file's age to decide whether the bridge has gone "alive but
mute".

Why a dedicated node instead of watching mir_raw.py's stdout: the bridge node is
named 'rosbridge_explorer', so every line it logs contains "[rosbridge_explorer]:"
and the old entrypoint filtered exactly those out -- meaning nothing refreshed the
heartbeat during healthy operation and the watchdog killed a healthy bridge on a
timer. This node measures the REAL end-to-end path (MiR rosbridge -> mir_raw.py ->
ROS2), which is what we actually care about.

This is our code (not Eemil's mir_raw.py). It only subscribes; it never commands
the robot.
"""
import os

import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry

HEARTBEAT = os.environ.get("MIR_BRIDGE_HEARTBEAT", "/tmp/mir_bridge_last_io")
TOPIC = os.environ.get("MIR_LIVENESS_TOPIC", "/odom")


class Liveness(Node):
    def __init__(self):
        super().__init__("mir_bridge_liveness")
        # Depth-10 reliable matches the bridge's default publisher QoS.
        self.create_subscription(Odometry, TOPIC, self._on_msg, 10)
        self.get_logger().info(f"watching {TOPIC} -> heartbeat {HEARTBEAT}")

    def _on_msg(self, _msg):
        try:
            # Create-if-missing, then bump mtime to "now".
            open(HEARTBEAT, "a").close()
            os.utime(HEARTBEAT, None)
        except OSError as exc:
            self.get_logger().warn(f"could not touch heartbeat: {exc}")


def main():
    rclpy.init()
    node = Liveness()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
