FROM ros2humble_dev_base:latest

COPY scripts/camera_entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

CMD ["bash", "/entrypoint.sh"]

