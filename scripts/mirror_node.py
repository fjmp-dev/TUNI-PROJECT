import rclpy
from rclpy.node import Node
import threading
import roslibpy
import time

from geometry_msgs.msg import Twist, TwistStamped, Pose
from std_msgs.msg import Header
from builtin_interfaces.msg import Time
import termios
import tty, sys




def get_key(settings):
    tty.setraw(sys.stdin.fileno())
    key = sys.stdin.read(1)
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)
    return key

def generate_roslibpy_header(frame_id='world'):
    now = time.time()
    secs = int(now)
    nsecs = int((now - secs) * 1e9)

    return {
        'stamp': {
            'secs': secs,
            'nsecs': nsecs
        },
        'frame_id': frame_id
    }

class CmdVelForwarder(Node):
    def __init__(self, rosbridge_host, rosbridge_port):
        super().__init__('CmdVelForwarder')

        self.rosbridge_host = rosbridge_host
        self.rosbridge_port = rosbridge_port
        self.remote_topic = '/cmd_vel'
        self.local_topic_in = '/cmd_vel_echo'
        self.local_topic_out = '/cmd_vel'

        self.get_logger().info(f'Connecting to rosbridge at {self.rosbridge_host}:{self.rosbridge_port}')
        self.ros_client = roslibpy.Ros(host=self.rosbridge_host, port=self.rosbridge_port)
        self.ros_client.run()

        self.remote_publisher = roslibpy.Topic(self.ros_client, self.remote_topic, 'geometry_msgs/TwistStamped')
        self.remote_subscriber = roslibpy.Topic(self.ros_client, self.remote_topic, 'geometry_msgs/TwistStamped')
        self.remote_subscriber.subscribe(self.roslibpy_to_ros2_callback)

        self.local_publisher = self.create_publisher(TwistStamped, self.local_topic_out, 10)
        self.local_subscriber = self.create_subscription(Twist, self.local_topic_in, self.ros2_to_roslibpy_callback, 10)
        print('CmdVelForwarder initialized')
        self.loop_thread = threading.Thread(target=self.teleop)
        self.loop_thread.start()

    def teleop(self):
        move_bindings = {
            'a': (0, 0.1),
            'w': (0.05, 0),
            's': (-0.05, 0),
            'd': (0, -0.1),
        }

        while rclpy.ok():
            key = get_key(termios.tcgetattr(sys.stdin))
            if key in move_bindings.keys():
                x = move_bindings[key][0]
                th = move_bindings[key][1]
            else:
                x = 0
                th = 0
                if (key == '\x03'): break
            
            message = {
                'header': generate_roslibpy_header(),
                'twist': {
                    'linear': {
                        'x': x,
                        'y': 0,
                        'z': 0
                    },
                    'angular': {
                        'x': 0,
                        'y': 0,
                        'z': th
                    }
                }
            }
            self.remote_publisher.publish(message)

    def ros2_to_roslibpy_callback(self, msg: TwistStamped):
        self.get_logger().debug(f"Forwarding ROS 2 -> rosbridge: {msg}")
        message = {
            'header': generate_roslibpy_header(),
            'twist': {
                'linear': {
                    'x': msg.linear.x,
                    'y': msg.linear.y,
                    'z': msg.linear.z
                },
                'angular': {
                    'x': msg.angular.x,
                    'y': msg.angular.y,
                    'z': msg.angular.z
                }
            }
        }
        self.remote_publisher.publish(message)
        # self.local_publisher.publish(message)

    def roslibpy_to_ros2_callback(self, message):
        self.get_logger().debug(f"Received rosbridge -> ROS 2: {message}")
        msg = TwistStamped()
        msg.header = Header()
        msg.header.stamp = Time()
        msg.header.stamp.sec = message['header']['stamp']['secs']
        msg.header.stamp.nanosec = message['header']['stamp']['nsecs']
        msg.header.frame_id = message['header'].get('frame_id', '')

        msg.twist.linear.x = message['twist']['linear']['x']
        msg.twist.linear.y = message['twist']['linear']['y']
        msg.twist.linear.z = message['twist']['linear']['z']
        msg.twist.angular.x = message['twist']['angular']['x']
        msg.twist.angular.y = message['twist']['angular']['y']
        msg.twist.angular.z = message['twist']['angular']['z']

        # self.local_publisher.publish(msg)

    def destroy_node(self):
        self.remote_publisher.unadvertise()
        self.remote_subscriber.unsubscribe()
        self.ros_client.terminate()
        super().destroy_node()


class RobotPoseForwarder(Node):
    def __init__(self, bridge_host, bridge_port):
        super().__init__('RobotPoseForwarder')

        # Setup rosbridge client
        self.client = roslibpy.Ros(host=bridge_host, port=bridge_port)
        self.client.run()
        self.get_logger().info(f"[rosbridge] Connected to {bridge_host}:{bridge_port}")

        self.client.get_topics(self._on_topics)

        self.topic_name = '/robot_pose'
        self.rosbridge_type = 'geometry_msgs/Pose'

        # ROS 2 publisher and subscriber
        self.local_publisher = self.create_publisher(Pose, self.topic_name, 10)
        self.local_subscriber = self.create_subscription(Pose, self.topic_name, self._local_to_remote_callback, 10)

        # rosbridge subscriber and publisher
        self.remote_sub = roslibpy.Topic(self.client, self.topic_name, self.rosbridge_type)
        self.remote_pub = roslibpy.Topic(self.client, self.topic_name, self.rosbridge_type)

        # Start listening to the remote topic
        self.remote_sub.subscribe(self._remote_to_local_callback)
        print('RobotPoseForwarder initialized')

    def _on_topics(self, topics):
        self.get_logger().info("Available Topics:")
        for topic in topics['topics']:
            # self.get_logger().info(f" - {topic} - {self.client.get_topic_type(topic)}")
            self.get_logger().info(f" - {topic}")
            def log_type(result, t=topic):
                self.get_logger().info(f" - {t} - {result['type']}")
            self.client.get_topic_type(topic, log_type)

    def _remote_to_local_callback(self, message):
        """Convert Pose from remote ROS (rosbridge) to local ROS 2."""
        msg = Pose()
        msg.position.x = message['position']['x']
        msg.position.y = message['position']['y']
        msg.position.z = message['position']['z']
        msg.orientation.x = message['orientation']['x']
        msg.orientation.y = message['orientation']['y']
        msg.orientation.z = message['orientation']['z']
        msg.orientation.w = message['orientation']['w']
        self.local_publisher.publish(msg)
        self.get_logger().debug("[rosbridge → ROS 2] Republished Pose")

    def _local_to_remote_callback(self, msg):
        """Convert Pose from local ROS 2 to remote ROS (rosbridge)."""
        message = {
            'position': {
                'x': msg.position.x,
                'y': msg.position.y,
                'z': msg.position.z
            },
            'orientation': {
                'x': msg.orientation.x,
                'y': msg.orientation.y,
                'z': msg.orientation.z,
                'w': msg.orientation.w
            }
        }
        self.remote_pub.publish(roslibpy.Message(message))
        self.get_logger().debug("[ROS 2 → rosbridge] Published Pose")

    def destroy_node(self):
        """Cleanup ROS bridge and node."""
        self.remote_sub.unsubscribe()
        self.remote_pub.unadvertise()
        self.client.terminate()
        super().destroy_node()

def main():
        

    rclpy.init()
    node = BidirectionalMirror('192.168.1.13', 9090)

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("Shutting down bidirectional mirror...")
    finally:
        node.destroy_node()
        rclpy.shutdown()

def main(args=None):
    rclpy.init(args=args)

    # node1 = RobotPoseForwarder('192.168.1.13', 9090)
    node2 = CmdVelForwarder('192.168.1.13', 9090)

    
    executor = rclpy.executors.MultiThreadedExecutor()
    # executor.add_node(node1)
    executor.add_node(node2)
    executor.spin()

    move_bindings = {
        'a': (0, 0.05),
        'w': (0.05, 0),
        's': (-0.05, 0),
        'd': (0, -0.05),
    }

    while True:
        key = get_key(termios.tcgetattr(sys.stdin))
        if key in move_bindings.keys():
            x = move_bindings[key][0]
            th = move_bindings[key][1]
        else:
            x = 0
            th = 0
            if (key == '\x03'): break
        
        message = {
            'header': generate_roslibpy_header(),
            'twist': {
                'linear': {
                    'x': x,
                    'y': 0,
                    'z': 0
                },
                'angular': {
                    'x': 0,
                    'y': 0,
                    'z': th
                }
            }
        }
        node2.remote_publisher.publish(message)
    
    rclpy.shutdown()
    executor_thread.join()

if __name__ == '__main__':
    threading.Thread(target=main).start()
