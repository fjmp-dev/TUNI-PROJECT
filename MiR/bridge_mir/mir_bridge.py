"""Selective MiR rosbridge <-> ROS 2 bridge (adopted from Wael's fortis-uc1-tau TK32).

Bridges ONLY the topics listed in the YAML config (default /mir_topic_config.yaml):
  - "sub" topics flow MiR -> ROS 2 (scans, odom, tf, battery)
  - "pub" topics flow ROS 2 -> MiR (/cmd_vel: drive the base directly)

Replaces the old mir_raw.py, which republished EVERY MiR topic and flooded the
DDS domain shared with the UR driver. The MiR's own map->odom transform is
filtered out so a local SLAM can own localization.

Adaptations vs upstream: host comes from MIR_IP (no hardcoded IP), the topic
config is a plain bind-mounted file (no ament package share), the custom
MirState msg was dropped (robot state reaches the UI via REST), and a failed
rosbridge connection exits non-zero so the entrypoint's backoff loop retries.
"""
import os
import rclpy
from rclpy.qos import QoSProfile, DurabilityPolicy
from rclpy.node import Node
from rclpy.clock import Clock
import roslibpy
from std_msgs.msg import Float64
from sensor_msgs.msg import LaserScan
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Point, Quaternion, Twist, Vector3, TransformStamped
from tf2_msgs.msg import TFMessage
from tf2_ros import TransformBroadcaster
from tf2_ros.static_transform_broadcaster import StaticTransformBroadcaster
import yaml


## MESSAGE CONVERTERS ##
def tf_conv(msg):
    tf_msg = TFMessage()
    for t in msg['transforms']:
        ts = TransformStamped()
        ts.header.stamp = Clock().now().to_msg()
        ts.header.frame_id = t['header']['frame_id']
        ts.child_frame_id = t['child_frame_id']
        ts.transform.translation = Vector3(
            x=t['transform']['translation']['x'],
            y=t['transform']['translation']['y'],
            z=t['transform']['translation']['z']
        )
        ts.transform.rotation = Quaternion(
            x=t['transform']['rotation']['x'],
            y=t['transform']['rotation']['y'],
            z=t['transform']['rotation']['z'],
            w=t['transform']['rotation']['w']
        )
        tf_msg.transforms.append(ts)
    return tf_msg


def laser_conv(msg):
    scan = LaserScan()
    scan.header.stamp = Clock().now().to_msg()
    scan.header.frame_id = msg['header']['frame_id']
    scan.angle_min = msg['angle_min']
    scan.angle_max = msg['angle_max']
    scan.angle_increment = msg['angle_increment']
    scan.time_increment = msg['time_increment']
    scan.scan_time = msg['scan_time']
    scan.range_min = msg['range_min']
    scan.range_max = msg['range_max']
    scan.ranges = list(msg['ranges'])
    scan.intensities = list(msg['intensities'])
    return scan


def odom_conv(msg):
    odom = Odometry()
    odom.header.stamp = Clock().now().to_msg()
    odom.header.frame_id = msg['header']['frame_id']
    odom.child_frame_id = msg['child_frame_id']
    odom.pose.pose.position = Point(
        x=msg['pose']['pose']['position']['x'],
        y=msg['pose']['pose']['position']['y'],
        z=msg['pose']['pose']['position']['z']
    )
    odom.pose.pose.orientation = Quaternion(
        x=msg['pose']['pose']['orientation']['x'],
        y=msg['pose']['pose']['orientation']['y'],
        z=msg['pose']['pose']['orientation']['z'],
        w=msg['pose']['pose']['orientation']['w']
    )
    odom.pose.covariance = list(msg['pose']['covariance'])
    odom.twist.twist.linear = Vector3(
        x=msg['twist']['twist']['linear']['x'],
        y=msg['twist']['twist']['linear']['y'],
        z=msg['twist']['twist']['linear']['z']
    )
    odom.twist.twist.angular = Vector3(
        x=msg['twist']['twist']['angular']['x'],
        y=msg['twist']['twist']['angular']['y'],
        z=msg['twist']['twist']['angular']['z']
    )
    odom.twist.covariance = list(msg['twist']['covariance'])
    return odom


def cmd_vel_conv(msg):
    return {
        'header': {
            'stamp': {'secs': 0, 'nsecs': 0},
            'frame_id': 'base_link'
        },
        'twist': {
            'linear': {'x': msg.linear.x, 'y': msg.linear.y, 'z': msg.linear.z},
            'angular': {'x': msg.angular.x, 'y': msg.angular.y, 'z': msg.angular.z}
        }
    }


def std_msg_f64(msg):
    f64 = Float64()
    f64.data = msg['data']
    return f64


## CONSTANTS ##
TYPES = {
    "/f_scan": [LaserScan, laser_conv],
    "/b_scan": [LaserScan, laser_conv],
    "/odom": [Odometry, odom_conv],
    "/tf": [TFMessage, tf_conv],
    "/tf_static": [TFMessage, tf_conv, QoSProfile(depth=10, durability=DurabilityPolicy.TRANSIENT_LOCAL)],
    "/cmd_vel": [Twist, cmd_vel_conv],
    "/MC/battery_percentage": [Float64, std_msg_f64],
    "/scan": [LaserScan, laser_conv],
}


## FUNCTIONALITY ##
# Publishers (remote): ROS 2 -> MiR
class Publisher(object):
    def __init__(self, topic, node, client):
        self.topic = topic
        self.node = node
        self.client = client
        self.converter = TYPES[topic["topic"]][1]

        self.pub_remote = roslibpy.Topic(client, topic["topic"], topic["type"])
        self.sub_local = node.create_subscription(
            TYPES[topic["topic"]][0],
            topic["topic"],
            self.callback,
            1,
        )
        node.get_logger().info(f"Publishing to MiR: {self.topic['topic']}")

    def callback(self, msg):
        if not rclpy.ok():
            return
        self.pub_remote.publish(self.converter(msg))


# Subscribers (remote): MiR -> ROS 2
class Subscriber(object):
    def __init__(self, topic, node, client):
        self.last_static_msg = None
        self.topic = topic
        self.node = node
        self.client = client
        self.converter = TYPES[topic["topic"]][1]

        self.tf_broadcaster = TransformBroadcaster(self.node)
        self.tf_static_broadcaster = StaticTransformBroadcaster(self.node)

        self.pub_local = node.create_publisher(
            TYPES[topic["topic"]][0],
            topic["topic"],
            1 if topic["topic"] != "/tf_static" else TYPES[topic["topic"]][2],
        )
        self.sub_remote = roslibpy.Topic(client, topic["topic"], topic["type"])
        if self.topic["topic"] == "/tf_static":
            self.sub_remote.subscribe(self.tf_static_callback)
        else:
            self.sub_remote.subscribe(self.callback)
        node.get_logger().info(f"Subscribed to MiR: {self.topic['topic']}")

    def callback(self, msg):
        if not rclpy.ok():
            return
        ros2_msg = self.converter(msg)

        # Filter out the MiR's map->odom transform so a local SLAM owns localization.
        if isinstance(ros2_msg, TFMessage):
            ros2_msg.transforms = [
                t for t in ros2_msg.transforms
                if not (t.header.frame_id == "map" and t.child_frame_id == "odom")
            ]
            if not ros2_msg.transforms:
                return
            for t in ros2_msg.transforms:
                self.tf_broadcaster.sendTransform(t)
        else:
            self.pub_local.publish(ros2_msg)

    def tf_static_callback(self, msg):
        if not rclpy.ok():
            return
        ros2_msg = self.converter(msg)
        ros2_msg.transforms = [
            t for t in ros2_msg.transforms
            if not (t.header.frame_id == "map" and t.child_frame_id == "odom")
        ]
        if not ros2_msg.transforms:
            return
        # Accumulate statics (the MiR sends them in several batches) and restamp
        # so late subscribers get the full set.
        if self.last_static_msg is None:
            self.last_static_msg = ros2_msg
        else:
            self.last_static_msg.transforms.extend(ros2_msg.transforms)
        now = self.node.get_clock().now().to_msg()
        for t in self.last_static_msg.transforms:
            t.header.stamp = now
        self.tf_static_broadcaster.sendTransform(self.last_static_msg.transforms)


# The bridge
class MiR_Bridge(Node):
    def __init__(self, rosbridge_host=None, rosbridge_port=9090):
        super().__init__('mir_bridge')
        host = rosbridge_host or os.getenv('MIR_IP', '192.168.1.13')

        self.target_topics = {}
        self.used_topics = {}
        self.pubs = []
        self.subs = []

        # Connect to the MiR's rosbridge; on failure exit non-zero so the
        # entrypoint's backoff loop handles the retry cadence.
        try:
            self.client = roslibpy.Ros(host=host, port=rosbridge_port)
            self.client.run()
        except Exception as e:
            self.get_logger().error(f"rosbridge connect failed ({host}:{rosbridge_port}): {e}")
            raise SystemExit(1)
        self.get_logger().info(f"Connected to MiR rosbridge at {host}:{rosbridge_port}")

        config_file = os.getenv('MIR_TOPIC_CONFIG', '/mir_topic_config.yaml')
        with open(config_file, 'r') as f:
            data = yaml.safe_load(f)
            for target in data['topics']:
                self.target_topics[target['topic']] = target['pub/sub']

        self.client.get_topics(self._on_topics)

    def _on_topics(self, topics):
        try:
            topics_arr = list(topics["topics"])
            types_arr = list(topics["types"])
            for i, name in enumerate(topics_arr):
                if name not in self.target_topics:
                    continue
                spec = {"topic": name, "type": types_arr[i], "pub/sub": self.target_topics[name]}
                self.used_topics[name] = spec
                if spec["pub/sub"] == "sub":
                    self.subs.append(Subscriber(spec, self, self.client))
                else:
                    self.pubs.append(Publisher(spec, self, self.client))
            missing = set(self.target_topics) - set(self.used_topics)
            if missing:
                self.get_logger().warn(f"Topics not offered by the MiR: {sorted(missing)}")
        except Exception as e:
            self.get_logger().error(str(e))


def main(args=None):
    rclpy.init(args=args)
    bridge = MiR_Bridge()
    try:
        rclpy.spin(bridge)
    except KeyboardInterrupt:
        bridge.get_logger().warn("Shutdown called")


if __name__ == '__main__':
    main()
