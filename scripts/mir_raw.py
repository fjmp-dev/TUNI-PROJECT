import rclpy
from rclpy.node import Node
import roslibpy
import importlib

from rclpy_message_converter import message_converter
from rosidl_runtime_py import message_to_ordereddict
from builtin_interfaces.msg import Time

def fix_ros1_to_ros2(d):
    if isinstance(d, dict):
        # Handle ROS1 -> ROS2 Time
        if 'secs' in d or 'nsecs' in d:
            return {
                'sec': d.get('secs', 0),
                'nanosec': d.get('nsecs', 0)
            }
        # Handle ROS1 -> ROS2 Header (remove seq)
        if 'stamp' in d and 'frame_id' in d:
            new_d = {k: fix_ros1_to_ros2(v) for k, v in d.items()}
            new_d.pop('seq', None)
            return new_d
        # Handle DiagnosticStatus.level
        if 'level' in d and isinstance(d['level'], int):
            val = d['level']
            # Clamp into [0,255] to make valid byte
            if val < 0:
                val = 0
            elif val > 255:
                val = 255
            d = dict(d)  # copy
            d['level'] = bytes([val])

        
        return {k: fix_ros1_to_ros2(v) for k, v in d.items()}
    elif isinstance(d, list):
        return [fix_ros1_to_ros2(v) for v in d]
    else:
        return d


def normalize_msg(msg):
    if hasattr(msg, "header"):
        msg["header"] = normalize_msg(msg.header)

    if isinstance(msg, dict):
        # print(msg)
        # Special case for CameraInfo field renames
        if 'D' in msg or 'K' in msg or 'R' in msg or 'P' in msg:
            msg = {
                **msg,
                'd': msg.pop('D', []),
                'k': msg.pop('K', []),
                'r': msg.pop('R', []),
                'p': msg.pop('P', []),
            }
            del msg['D']
            del msg['K']
            del msg['R']
            del msg['P']
        return {
            k: normalize_msg(v) if isinstance(v, (dict, list)) or hasattr(v, '__slots__') else v
            for k, v in msg.items()
        }

    elif isinstance(msg, list):
        return [normalize_msg(v) for v in msg]

    elif hasattr(msg, '__slots__'):
        return message_to_ordereddict(msg)

    return msg

def dict_to_rosmsg(msg_class, data: dict):
    obj = msg_class()
    for field, field_type in obj.get_fields_and_field_types().items():
        if field not in data:
            continue
        value = data[field]
        if hasattr(getattr(obj, field), '__slots__'):  # submessage
            sub_class = type(getattr(obj, field))
            setattr(obj, field, dict_to_rosmsg(sub_class, value))
        else:
            setattr(obj, field, value)
    return obj


class RosbridgeExplorer(Node):
    def __init__(self, rosbridge_host='192.168.1.13', rosbridge_port=9090):
        super().__init__('rosbridge_explorer')

        # Connect to rosbridge
        self.client = roslibpy.Ros(host=rosbridge_host, port=rosbridge_port)
        self.client.run()

        if not self.client.is_connected:
            self.get_logger().error('Failed to connect to rosbridge.')
            return

        self.get_logger().info(f"Connected to rosbridge at ws://{rosbridge_host}:{rosbridge_port}")

        # Explore topics
        self.client.get_topics(self._on_topics)

        self.__subscribers = {}
        self.__publishers = {}

        # # Explore services
        # self.client.get_services(self._on_services)

        # # Explore parameters
        # self.client.get_params(self._on_params)

    def _on_topics(self, topics):
        self.get_logger().info("Available Topics:")

        for topic in topics['topics']:
            def log_type(result, t=topic):
                self.get_logger().info(f" - {t} - {result['type']}")

                if 'mir' in result['type'] or \
                    'dynamic_reconfigure' in result['type'] or \
                    'sdc21x0' in result['type'] or \
                    'rosgraph_msgs/Log' in result['type'] or \
                    'sbpl_lattice_planner_msgs' in result['type']:
                    return
                try:
                    pkg_name, msg_name = result['type'].split('/')
                    # self.get_logger().error(f"Failed to convert {msg_name}: {e}")
                    try:
                        if pkg_name.startswith("realsense2_camera"):
                            pkg_name = pkg_name.replace("realsense2_camera", "realsense2_camera_msgs")

                        msg_module = importlib.import_module(f"{pkg_name}.msg")
                        msg_class = getattr(msg_module, msg_name)
                    except ModuleNotFoundError:
                        self.get_logger().warn(f"Skipping {t}: {pkg_name}/{msg_name} not available in ROS2")
                        return
                    # finally:
                    
                    # Remote subscriber
                    self.__subscribers[msg_name] = roslibpy.Topic(self.client, t, result['type'])

                    # Local publisher
                    self.__publishers[msg_name] = self.create_publisher(msg_class, t, 10)

                    # Forward callback
                    # def forwarding(msg, msg_class=msg_class, ros2_pub=self.__publishers[msg_name]):
                    #     # ros2_msg = msg_class(**msg)   # dict -> ROS2 message
                    #     ros2_msg = dict_to_rosmsg(msg_class, msg)
                    #     ros2_pub.publish(ros2_msg)

                    def forwarding(msg, msg_class=msg_class, ros2_pub=self.__publishers[msg_name]):
                        try:
                            dict_msg = normalize_msg(msg)
                            dict_msg = fix_ros1_to_ros2(dict_msg)
                            # print(msg, dict_msg)
                            ros2_msg = message_converter.convert_dictionary_to_ros_message(
                                f"{pkg_name}/msg/{msg_name}", dict_msg
                                # result['type'], dict_msg
                            )
                            ros2_pub.publish(ros2_msg)
                        except Exception as e:
                            self.get_logger().error(f"Failed to convert {msg_class} {msg_name}: {e}")


                    self.__subscribers[msg_name].subscribe(forwarding)

                except Exception as e:
                    self.get_logger().error(f"Failed to bridge {t} ({result['type']}): {e}")
            # self.get_logger().info(f" - {topic} - {self.client.get_topic_type(topic)}")
            # self.get_logger().info(f" - {topic}")
            
            self.client.get_topic_type(topic, log_type)

    def _on_services(self, services):
        self.get_logger().info("Available Services:")
        for service in services['services']:
            self.get_logger().info(f" - {service}")

    def _on_params(self, params):
        self.get_logger().info("Available Parameters:")
        for param in params:
            self.get_logger().info(f" - {param}")


def main(args=None):
    rclpy.init(args=args)
    explorer = RosbridgeExplorer()

    try:
        # rclpy.spin_once(explorer, timeout_sec=5.0)
        rclpy.spin(explorer)
    finally:
        explorer.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()