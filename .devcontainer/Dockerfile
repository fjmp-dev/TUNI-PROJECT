# Dev container image: same ROS2 Humble environment the project uses.
# Requires the base image to exist (see ../base_image/README.md).
FROM ros2humble_dev_base:latest

# Handy tools for developing inside the container
RUN pip3 install --no-cache-dir roslibpy || true

WORKDIR /workspace
CMD ["sleep", "infinity"]
