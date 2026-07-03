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
    """Fetch the latest joint positions from joint_server (:9091).

    Raises RuntimeError with a clear message on any failure (server down,
    timeout, malformed response, or a server-side error payload) so the caller
    ABORTS the move instead of silently falling back to a 0.0 baseline — moving
    from a phantom 0.0 current position could command a large, unexpected jump.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    try:
        sock.connect(('127.0.0.1', 9091))
        sock.sendall(b'GET /joints HTTP/1.0\r\n\r\n')
        data = b''
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk
    except (socket.timeout, OSError) as e:
        raise RuntimeError(f'cannot reach joint_server on :9091 ({e})')
    finally:
        sock.close()

    parts = data.split(b'\r\n\r\n', 1)
    if len(parts) < 2 or not parts[1].strip():
        raise RuntimeError('empty/invalid response from joint_server')
    try:
        body = json.loads(parts[1])
    except (ValueError, json.JSONDecodeError) as e:
        raise RuntimeError(f'bad JSON from joint_server ({e})')
    if isinstance(body, dict) and body.get('error'):
        raise RuntimeError(f'joint_server error: {body["error"]}')
    return body


class Mover(Node):
    def __init__(self):
        super().__init__('one_shot_mover')
        # Use joint_trajectory_controller (the scaled one does not work: it accepts goals but never completes them)
        self.left_client = ActionClient(
            self, FollowJointTrajectory,
            '/left_joint_trajectory_controller/follow_joint_trajectory')
        self.right_client = ActionClient(
            self, FollowJointTrajectory,
            '/right_joint_trajectory_controller/follow_joint_trajectory')

    def move_joint(self, side, joint_short, delta):
        client = self.left_client if side == 'left' else self.right_client
        if not client.wait_for_server(timeout_sec=8.0):
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

        # Estado actual via joint_server. Abortamos si falla o falta algun joint:
        # nunca partir de un 0.0 fantasma (commandaria un salto grande inesperado).
        try:
            d = get_joints()
        except RuntimeError as e:
            return False, str(e)
        current = d.get(side)
        if not current:
            return False, f'no joint data for {side} arm (cannot move safely)'
        current_full = []
        for n in full_names:
            short = n.replace(f'{side}_', '')
            if short not in current:
                return False, f'missing {short} in joint data (cannot move safely)'
            current_full.append(current[short])
        target_full = list(current_full)
        target_full[idx] += delta

        goal = FollowJointTrajectory.Goal()
        goal.trajectory = JointTrajectory()
        goal.trajectory.joint_names = full_names
        # ONE target point only — let the controller interpolate from the arm's
        # ACTUAL current state. A t=0 start point set to the (slightly stale) read
        # position makes the controller command an instant correction → a velocity
        # spike that trips the robot's safety speed limit → protective stop (which
        # stops the external program). A slower duration keeps speed well under it.
        duration = max(3.0, abs(delta) * 60.0)  # 0.1 rad = 6s, 0.01 = 3s
        p_target = JointTrajectoryPoint()
        p_target.positions = target_full
        p_target.time_from_start.sec = int(duration)
        p_target.time_from_start.nanosec = int((duration - int(duration)) * 1e9)
        goal.trajectory.points = [p_target]

        future = client.send_goal_async(goal)
        # 10s (not 5s): joint_mover spins up a fresh node + ActionClient every move,
        # and DDS discovery/handshake of the action server occasionally exceeds 5s
        # under load. A tight timeout left handle=None -> AttributeError crash.
        rclpy.spin_until_future_complete(self, future, timeout_sec=10.0)
        handle = future.result()
        if handle is None:
            return False, ('timeout waiting for goal acceptance '
                           '(action server slow/unavailable)')
        if not handle.accepted:
            return False, 'goal rejected'

        result_future = handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future, timeout_sec=15.0)
        result = result_future.result()
        if result is None:
            return False, 'timeout waiting for result (controller busy or previous goal still running)'
        if result.status == 4:  # SUCCEEDED
            # The controller can report SUCCEEDED while the UR external-control
            # program is stopped, leaving the arm exactly where it was. Verify the
            # joint actually moved; if not, report a recoverable "no motion" so the
            # backend resends the program and retries.
            try:
                time.sleep(0.2)
                key = full_names[idx].replace(f'{side}_', '')
                new_val = get_joints().get(side, {}).get(key)
                # Skip the check for tiny moves (< 0.02 rad): they sit within the
                # controller's settle tolerance and would false-flag as "no motion".
                if (new_val is not None and abs(delta) >= 0.02
                        and abs(new_val - current_full[idx]) < 0.5 * abs(delta)):
                    return False, ('no motion: arm did not move (UR external '
                                   'program not running?)')
            except RuntimeError:
                pass  # can't verify; assume the move went through
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
