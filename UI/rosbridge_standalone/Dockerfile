FROM mir-base:latest

EXPOSE 9090

CMD ["bash", "-c", "source /opt/ros/humble/setup.bash && ros2 launch rosbridge_server rosbridge_websocket_launch.xml port:=9090"]