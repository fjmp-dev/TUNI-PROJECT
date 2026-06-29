FROM ros2humble_dev_base:latest

RUN pip3 install --no-cache-dir roslibpy

COPY scripts/mir_entrypoint.sh /entrypoint.sh
COPY scripts/mir_raw.py /mir_raw.py
COPY scripts/mir_watchdog.sh /mir_watchdog.sh
COPY scripts/mir_liveness.py /mir_liveness.py
RUN chmod +x /entrypoint.sh /mir_watchdog.sh

CMD ["bash", "/entrypoint.sh"]

