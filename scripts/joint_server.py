#!/usr/bin/env python3
"""
Servidor HTTP persistente que se suscribe a /joint_states una sola vez
y sirve los datos en el puerto 9091. Mucho más eficiente que lanzar un
proceso por cada petición.
"""
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import time

LATEST = {"msg": None, "ts": 0.0}
LOCK = threading.Lock()


class JointSub(Node):
    def __init__(self):
        super().__init__('joint_server')
        from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy, HistoryPolicy
        qos = QoSProfile(
            depth=1,
            durability=DurabilityPolicy.VOLATILE,
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
        )
        self.create_subscription(JointState, '/joint_states', self._cb, qos)

    def _cb(self, msg):
        with LOCK:
            LATEST["msg"] = msg
            LATEST["ts"] = time.time()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/joints':
            with LOCK:
                msg = LATEST["msg"]
                age = time.time() - LATEST["ts"] if LATEST["ts"] > 0 else 999
            if msg is None:
                self._json(503, {"error": "no joint data yet", "stale": True})
                return
            names = list(msg.name)
            pos = list(msg.position)
            data = {
                "names": names,
                "position": pos,
                "left": {},
                "right": {},
                "age_s": round(age, 3),
                "stale": age > 2.0,
            }
            for n, p in zip(names, pos):
                if n.startswith("left_"):
                    data["left"][n[5:]] = p
                elif n.startswith("right_"):
                    data["right"][n[6:]] = p
            self._json(200, data)
        elif self.path == '/health':
            self._json(200, {"ok": True})
        else:
            self._json(404, {"error": "not found"})

    def _json(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def main():
    rclpy.init()
    node = JointSub()
    t = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    t.start()
    srv = ThreadingHTTPServer(("0.0.0.0", 9091), Handler)
    print("[joint_server] listening on :9091", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
