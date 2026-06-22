#!/usr/bin/env python3
"""Lee /joint_states via rclpy y devuelve un JSON con los joints.
Se usa desde el backend FastAPI via docker exec.
"""
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
import json
import sys


class JointReader(Node):
    def __init__(self):
        super().__init__('joint_reader_once')
        self.msg = None

        # transient_local QoS para recibir el último mensaje
        from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy
        qos = QoSProfile(
            depth=1,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            reliability=ReliabilityPolicy.RELIABLE,
        )
        self.sub = self.create_subscription(
            JointState, '/joint_states', self._cb, qos)

    def _cb(self, msg):
        if self.msg is None:
            self.msg = msg


def main():
    rclpy.init()
    node = JointReader()

    # Esperar hasta 4 segundos por el primer mensaje
    import time
    deadline = time.time() + 4.0
    while time.time() < deadline and node.msg is None:
        rclpy.spin_once(node, timeout_sec=0.1)

    if node.msg is None:
        print(json.dumps({"error": "timeout waiting for /joint_states"}))
        sys.exit(1)

    msg = node.msg
    names = list(msg.name)
    pos = list(msg.position)
    data = {
        "names": names,
        "position": pos,
        "left": {},
        "right": {},
        "ts": time.time(),
    }
    for n, p in zip(names, pos):
        if n.startswith("left_"):
            data["left"][n[5:]] = p
        elif n.startswith("right_"):
            data["right"][n[6:]] = p

    print(json.dumps(data))
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
