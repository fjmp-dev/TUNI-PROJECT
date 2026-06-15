#!/usr/bin/env python3
"""
action_bridge.py — JSON command bridge for MIR Suite.

Receives commands via /mir/command (std_msgs/String, JSON).
Publishes results on /mir/status (std_msgs/String, JSON).

Supports:
  - Left arm: /move_to_pose_in_frame (moveit_interface_node)
  - Right arm: /move_action (MoveIt move_group)
  - Right arm home: joint-space MoveGroup goal to a saved safe configuration
  - Hand: /left_humanoid_hand/close_hand, open_hand

Safety notes:
  - Right-arm cartesian goals keep the current TCP orientation so the wrist
    does not twist unexpectedly.
  - Velocity/acceleration are capped at very conservative values for real HW.
"""

import json
import os
from pathlib import Path

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from std_msgs.msg import String

# Safe right-arm joint configuration (fallback values).
# Update /mir/config/right_safe_pose.json and restart the bridge to refresh.
DEFAULT_RIGHT_SAFE_JOINTS = {
    'right_shoulder_pan_joint': 0.260066,
    'right_shoulder_lift_joint': -2.511969,
    'right_elbow_joint': -1.541838,
    'right_wrist_1_joint': -0.292104,
    'right_wrist_2_joint': 1.095833,
    'right_wrist_3_joint': -6.021772,
}

SAFE_CONFIG_PATHS = [
    Path('/mir/config/right_safe_pose.json'),
    Path(__file__).parent.parent / 'config' / 'right_safe_pose.json',
]


def load_safe_joints():
    for p in SAFE_CONFIG_PATHS:
        if p.exists():
            try:
                with open(p) as f:
                    data = json.load(f)
                # Accept both flat dict and nested formats
                if isinstance(data, dict):
                    if all(isinstance(v, (int, float)) for v in data.values()):
                        return data
                    joints = data.get('joints', data.get('right', {}))
                    if joints:
                        return joints
            except Exception:
                pass
    return DEFAULT_RIGHT_SAFE_JOINTS


class ActionBridge(Node):
    def __init__(self):
        super().__init__('mir_action_bridge')

        self.status_pub = self.create_publisher(String, '/mir/status', 10)
        self.create_subscription(String, '/mir/command', self.on_command, 10)

        # TF for keeping current right TCP orientation
        from tf2_ros import Buffer, TransformListener
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        # Lazy-init action clients
        self._close_hand_client = None
        self._open_hand_client = None
        self._move_left_client = None
        self._move_right_client = None

        self._right_safe_joints = load_safe_joints()
        self.get_logger().info(
            f'ActionBridge ready — listening on /mir/command; '
            f'right safe joints loaded: {list(self._right_safe_joints.keys())}'
        )

    def on_command(self, msg):
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError as e:
            self.log(f'Invalid JSON: {e}', 'error')
            return

        cmd = data.get('command', '')
        args = data.get('args', {})

        if cmd == 'close_hand':
            self.close_hand(args)
        elif cmd == 'open_hand':
            self.open_hand()
        elif cmd == 'move_arm':
            self.move_arm(args)
        elif cmd == 'home':
            self.go_home(args)
        elif cmd == 'stop_arm':
            self.stop_arm()
        else:
            self.log(f'Unknown command: {cmd}', 'error')

    # ============================================================
    # Hand control
    # ============================================================
    def close_hand(self, args):
        from interfaces_pkg.action import CloseHand
        if self._close_hand_client is None:
            self._close_hand_client = ActionClient(self, CloseHand, '/left_humanoid_hand/close_hand')

        if not self._close_hand_client.wait_for_server(timeout_sec=2.0):
            self.log('CloseHand action server not available', 'error')
            return

        grasp = args.get('grasp_type', 'largediameter')
        max_currents = args.get('max_currents', [20, 20, 5, 5, 5, 5])

        goal = CloseHand.Goal()
        goal.grasp_type = grasp
        goal.max_currents = max_currents

        self.log(f'Closing hand: grasp={grasp}')
        self._close_hand_client.send_goal_async(goal).add_done_callback(
            lambda f: self._on_result(f, 'close_hand')
        )

    def open_hand(self):
        from interfaces_pkg.action import OpenHand
        if self._open_hand_client is None:
            self._open_hand_client = ActionClient(self, OpenHand, '/left_humanoid_hand/open_hand')

        if not self._open_hand_client.wait_for_server(timeout_sec=2.0):
            self.log('OpenHand action server not available', 'error')
            return

        goal = OpenHand.Goal()
        self.log('Opening hand')
        self._open_hand_client.send_goal_async(goal).add_done_callback(
            lambda f: self._on_result(f, 'open_hand')
        )

    # ============================================================
    # Arm movement
    # ============================================================
    def move_arm(self, args):
        side = args.get('side', 'left')

        if side == 'right':
            self.move_right_arm(args)
        else:
            self.move_left_arm(args)

    def _clamp_velocity(self, v):
        """Keep real-HW velocities very conservative."""
        try:
            v = float(v)
        except (TypeError, ValueError):
            v = 0.02
        return max(0.001, min(v, 0.10))

    def _get_current_tcp_orientation(self, frame):
        """Lookup current right_tool0 orientation w.r.t. frame; return None on failure."""
        from geometry_msgs.msg import Quaternion
        try:
            trans = self.tf_buffer.lookup_transform(
                frame, 'right_tool0', rclpy.time.Time(), timeout=rclpy.duration.Duration(seconds=0.5)
            )
            q = trans.transform.rotation
            return Quaternion(x=q.x, y=q.y, z=q.z, w=q.w)
        except Exception as e:
            self.log(f'TF lookup right_tool0 -> {frame} failed: {e}', 'warn')
            return None

    def move_left_arm(self, args):
        from interfaces_pkg.action import MoveToPoseInFrame
        if self._move_left_client is None:
            self._move_left_client = ActionClient(self, MoveToPoseInFrame, '/move_to_pose_in_frame')

        if not self._move_left_client.wait_for_server(timeout_sec=3.0):
            self.log('MoveToPoseInFrame (left) not available', 'error')
            return

        goal = MoveToPoseInFrame.Goal()
        goal.frame = args.get('frame', 'table_corner')
        goal.x = float(args.get('x', 0.0))
        goal.y = float(args.get('y', 0.0))
        goal.z = float(args.get('z', 0.2))
        goal.rx = float(args.get('rx', 0.0))
        goal.ry = float(args.get('ry', 0.0))
        goal.rz = float(args.get('rz', 0.0))
        goal.rw = float(args.get('rw', 1.0))
        goal.velocity_scaling_factor = self._clamp_velocity(args.get('velocity', 0.05))
        goal.use_cartesian_path = bool(args.get('cartesian', True))
        goal.allow_exec_partial_path = bool(args.get('partial', False))

        v = goal.velocity_scaling_factor
        x, y, z = goal.x, goal.y, goal.z
        self.log(f'Move LEFT: xyz=[{x:.3f},{y:.3f},{z:.3f}] vel={v:.3f}')
        self._move_left_client.send_goal_async(goal).add_done_callback(
            lambda f: self._on_result(f, 'move_arm')
        )

    def move_right_arm(self, args):
        from moveit_msgs.action import MoveGroup
        from moveit_msgs.msg import MotionPlanRequest, Constraints, PositionConstraint
        from shape_msgs.msg import SolidPrimitive
        from geometry_msgs.msg import Pose, Point, Quaternion

        if self._move_right_client is None:
            self._move_right_client = ActionClient(self, MoveGroup, '/move_action')

        if not self._move_right_client.wait_for_server(timeout_sec=3.0):
            self.log('/move_action not available for right arm', 'error')
            return

        x = float(args.get('x', 0.0))
        y = float(args.get('y', 0.0))
        z = float(args.get('z', 0.2))
        velocity = self._clamp_velocity(args.get('velocity', 0.02))
        frame = args.get('frame', 'table_corner')

        sphere = SolidPrimitive()
        sphere.type = SolidPrimitive.SPHERE
        sphere.dimensions = [0.005]

        pose = Pose()
        pose.position = Point(x=x, y=y, z=z)

        # Keep current TCP orientation to avoid wrist twists. Fallback to identity.
        current_q = self._get_current_tcp_orientation(frame)
        pose.orientation = current_q if current_q is not None else Quaternion(x=0.0, y=0.0, z=0.0, w=1.0)

        pos_constraint = PositionConstraint()
        pos_constraint.header.frame_id = frame
        pos_constraint.link_name = 'right_tcp'
        pos_constraint.weight = 1.0
        pos_constraint.constraint_region.primitives.append(sphere)
        pos_constraint.constraint_region.primitive_poses.append(pose)

        constraints = Constraints()
        constraints.position_constraints.append(pos_constraint)

        request = MotionPlanRequest()
        request.group_name = 'right_ur_manipulator'
        request.allowed_planning_time = 10.0
        request.max_velocity_scaling_factor = velocity
        request.max_acceleration_scaling_factor = min(velocity, 0.03)
        request.num_planning_attempts = 5
        request.goal_constraints.append(constraints)
        request.workspace_parameters.header.frame_id = frame
        request.workspace_parameters.min_corner.x = -1.5
        request.workspace_parameters.min_corner.y = -1.5
        request.workspace_parameters.min_corner.z = -1.5
        request.workspace_parameters.max_corner.x = 1.5
        request.workspace_parameters.max_corner.y = 1.5
        request.workspace_parameters.max_corner.z = 1.5

        goal = MoveGroup.Goal()
        goal.request = request
        goal.planning_options.plan_only = False
        goal.planning_options.look_around = False

        orient_source = 'current' if current_q is not None else 'fallback'
        self.log(f'Move RIGHT: xyz=[{x:.3f},{y:.3f},{z:.3f}] vel={velocity:.3f} orient={orient_source}')
        self._move_right_client.send_goal_async(goal).add_done_callback(
            lambda f: self._on_result(f, 'move_arm')
        )

    def go_home(self, args):
        """Send the right arm to the saved safe joint configuration via MoveIt joint-space goal."""
        from moveit_msgs.action import MoveGroup
        from moveit_msgs.msg import MotionPlanRequest, Constraints, JointConstraint

        side = args.get('side', 'right')
        if side != 'right':
            self.log('Home command currently only supported for right arm', 'error')
            return

        if self._move_right_client is None:
            self._move_right_client = ActionClient(self, MoveGroup, '/move_action')

        if not self._move_right_client.wait_for_server(timeout_sec=3.0):
            self.log('/move_action not available for right arm home', 'error')
            return

        velocity = self._clamp_velocity(args.get('velocity', 0.02))

        constraints = Constraints()
        for name, value in self._right_safe_joints.items():
            jc = JointConstraint()
            jc.joint_name = name
            jc.position = float(value)
            jc.tolerance_above = 0.05
            jc.tolerance_below = 0.05
            jc.weight = 1.0
            constraints.joint_constraints.append(jc)

        request = MotionPlanRequest()
        request.group_name = 'right_ur_manipulator'
        request.allowed_planning_time = 10.0
        request.max_velocity_scaling_factor = velocity
        request.max_acceleration_scaling_factor = min(velocity, 0.03)
        request.num_planning_attempts = 5
        request.goal_constraints.append(constraints)

        goal = MoveGroup.Goal()
        goal.request = request
        goal.planning_options.plan_only = False
        goal.planning_options.look_around = False

        self.log(f'HOME RIGHT: vel={velocity:.3f}')
        self._move_right_client.send_goal_async(goal).add_done_callback(
            lambda f: self._on_result(f, 'home')
        )

    def stop_arm(self):
        self.log('Stopping arm movement')
        self.status({'action': 'stop_arm', 'result': 'ok'})

    def _on_result(self, future, action):
        try:
            goal_handle = future.result()
        except Exception as e:
            self.status({'action': action, 'result': f'error: {e}'})
            return

        if not goal_handle.accepted:
            self.status({'action': action, 'result': 'rejected'})
            return

        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(lambda f, a=action: self._on_final(f, a))

    def _on_final(self, future, action):
        try:
            result = future.result()
            ok = result.result.error_code.val == 1  # SUCCESS
            self.status({'action': action, 'result': 'ok' if ok else 'failed'})
        except Exception as e:
            self.status({'action': action, 'result': f'error: {e}'})

    # ============================================================
    # Helpers
    # ============================================================
    def log(self, msg, level='info'):
        self.get_logger().info(msg)
        if level != 'info':
            self.status({'event': msg, 'level': level})
        else:
            self.status({'event': msg})

    def status(self, data):
        data['ts'] = self.get_clock().now().nanoseconds // 1_000_000
        self.status_pub.publish(String(data=json.dumps(data)))


def main():
    rclpy.init()
    node = ActionBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
