#!/usr/bin/env python3
"""
Mueve un joint específico del UR5e.
Uso: python3 joint_mover.py <arm> <joint> <delta_rad>
  arm: left | right
  joint: shoulder_pan, shoulder_lift, elbow, wrist_1, wrist_2, wrist_3
  delta_rad: cambio en radianes (positivo o negativo)
"""
import sys
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from control_msgs.action import FollowJointTrajectory
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
import time
import json
import socket


def get_joints():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    sock.connect(('127.0.0.1', 9091))
    sock.sendall(b'GET /joints HTTP/1.0\r\n\r\n')
    data = b''
    while True:
        chunk = sock.recv(4096)
        if not chunk: break
        data += chunk
    sock.close()
    body = data.split(b'\r\n\r\n', 1)[1]
    return json.loads(body)


class Mover(Node):
    def __init__(self):
        super().__init__('one_shot_mover')
        # Usar joint_trajectory_controller (el scaled no funciona: acepta goals pero nunca los completa)
        self.left_client = ActionClient(
            self, FollowJointTrajectory,
            '/left_joint_trajectory_controller/follow_joint_trajectory')
        self.right_client = ActionClient(
            self, FollowJointTrajectory,
            '/right_joint_trajectory_controller/follow_joint_trajectory')

    def move_joint(self, side, joint_short, delta):
        client = self.left_client if side == 'left' else self.right_client
        if not client.wait_for_server(timeout_sec=5.0):
            return False, 'controller not available'

        # Mapeo de nombre corto a nombre completo
        full_names = [
            f'{side}_shoulder_pan_joint',
            f'{side}_shoulder_lift_joint',
            f'{side}_elbow_joint',
            f'{side}_wrist_1_joint',
            f'{side}_wrist_2_joint',
            f'{side}_wrist_3_joint',
        ]
        joint_index = {
            'shoulder_pan': 0, 'shoulder_lift': 1, 'elbow': 2,
            'wrist_1': 3, 'wrist_2': 4, 'wrist_3': 5,
        }
        if joint_short not in joint_index:
            return False, f'unknown joint: {joint_short}'

        idx = joint_index[joint_short]

        # Estado actual via joint_server
        d = get_joints()
        current = d.get(side, {})
        current_full = [current.get(n.replace(f'{side}_', ''), 0.0) for n in full_names]
        target_full = list(current_full)
        target_full[idx] += delta

        goal = FollowJointTrajectory.Goal()
        goal.trajectory = JointTrajectory()
        goal.trajectory.joint_names = full_names
        # Punto inicial = estado actual
        p_now = JointTrajectoryPoint()
        p_now.positions = current_full
        p_now.time_from_start.sec = 0
        p_now.time_from_start.nanosec = 0
        # Punto meta
        duration = max(2.0, abs(delta) * 30.0)  # 0.1 rad = 3s, 0.01 = 2s
        p_target = JointTrajectoryPoint()
        p_target.positions = target_full
        p_target.time_from_start.sec = int(duration)
        p_target.time_from_start.nanosec = int((duration - int(duration)) * 1e9)
        goal.trajectory.points = [p_now, p_target]

        future = client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)
        handle = future.result()
        if not handle.accepted:
            return False, 'goal rejected'

        result_future = handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future, timeout_sec=15.0)
        result = result_future.result()
        if result is None:
            return False, 'timeout waiting for result (controller busy or previous goal still running)'
        if result.status == 4:  # SUCCEEDED
            return True, f'moved {side} {joint_short} by {delta:+.4f} rad (from {current_full[idx]:.4f} to {target_full[idx]:.4f})'
        return False, f'failed status={result.status}'


def main():
    if len(sys.argv) != 4:
        print('Usage: joint_mover.py <arm> <joint> <delta>')
        print('  arm: left | right')
        print('  joint: shoulder_pan, shoulder_lift, elbow, wrist_1, wrist_2, wrist_3')
        print('  delta: float in radians')
        sys.exit(1)

    arm = sys.argv[1]
    joint = sys.argv[2]
    delta = float(sys.argv[3])

    if arm not in ('left', 'right'):
        print(f'Invalid arm: {arm}')
        sys.exit(1)

    rclpy.init()
    mover = Mover()
    ok, msg = mover.move_joint(arm, joint, delta)
    print(f'{"OK" if ok else "FAIL"}: {msg}')
    rclpy.shutdown()
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
