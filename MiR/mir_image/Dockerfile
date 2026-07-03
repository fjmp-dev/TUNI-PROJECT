FROM ros2humble_dev_base:latest

RUN pip3 install --no-cache-dir roslibpy

COPY MiR/mir_entrypoint/mir_entrypoint.sh /entrypoint.sh
COPY MiR/bridge_mir/mir_raw.py /mir_raw.py
COPY MiR/mir_watchdog/mir_watchdog.sh /mir_watchdog.sh
COPY MiR/mir_liveness/mir_liveness.py /mir_liveness.py
RUN chmod +x /entrypoint.sh /mir_watchdog.sh

CMD ["bash", "/entrypoint.sh"]

