FROM ros2humble_dev_base:latest

COPY PERIPHERAL/camera_orbbec/camera_entrypoint/camera_entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

CMD ["bash", "/entrypoint.sh"]