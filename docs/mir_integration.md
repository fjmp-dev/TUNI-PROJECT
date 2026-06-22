# MiR200 Integration Guide

## Overview

This document contains all the information about the MiR200 mobile robot integration with the MIR Suite system.

## Device Information

- **Name:** MiR_S455
- **Model:** MiR200
- **IP Address:** 192.168.1.13
- **MAC Address:** 34:41:5d:3e:55:f3
- **DNS:** 8.8.8.8, 8.8.4.4
- **Network:** 192.168.1.0/24 (Ethernet, same as Kevin)
- **Status:** Active and connected

## Network Connectivity

### Ping Test
- **ICMP:** Blocked by firewall (normal for industrial devices)
- **ARP:** ✅ Responsive (MAC address visible in ARP table)

### Open Ports

| Port | Service | Protocol | Status |
|------|---------|----------|--------|
| 22 | SSH | TCP | ✅ Open |
| 80 | HTTP (API REST) | TCP | ✅ Open |
| 443 | HTTPS | TCP | ✅ Open |
| 502 | Modbus TCP | TCP | ✅ Open |
| 8080 | Web Secondary | TCP | ✅ Open |
| 9090 | Rosbridge WebSocket | TCP | ✅ Open |

## API REST (v2.0.0)

### Base URL
```
http://192.168.1.13/api/v2.0.0/
```

### Authentication
Some endpoints require authentication. The `/status` endpoint works without authentication.

### Endpoints

#### Status (No Auth Required)
```bash
curl http://192.168.1.13/api/v2.0.0/status
```

**Response:**
```json
{
  "robot_name": "MiR_S455",
  "robot_model": "MiR200",
  "battery_percentage": 52.9,
  "mode_text": "Mission",
  "state_text": "Pause",
  "mode_id": 7,
  "state_id": 4,
  "uptime": 918,
  "moved": 51293.6,
  "errors": [],
  "safety_system_muted": false,
  "position": {
    "x": 12.47,
    "y": 11.34,
    "orientation": -5.06
  },
  "velocity": {
    "linear": 0.0,
    "angular": 0.0
  },
  "map_id": "3dbc3c4c-d0de-11e5-8ef2-94c691a3e36f",
  "session_id": "790ff779-d2df-11e8-a170-94c691a3e36f"
}
```

#### Other Endpoints (Auth Required)
- `/status/battery` - Battery information
- `/maps` - Available maps
- `/positions` - Saved positions
- `/missions` - Available missions
- `/mission_queue` - Mission queue

## ROS Integration

### Rosbridge WebSocket
- **URL:** `ws://192.168.1.13:9090`
- **Status:** ✅ Connected and responsive
- **Protocol:** ROS 1 (internal to MiR)

### Connection Test
```python
import websocket
import json

ws = websocket.create_connection("ws://192.168.1.13:9090", timeout=5)
ws.send(json.dumps({
    "op": "call_service",
    "service": "/rosapi/topics",
    "args": {}
}))
result = ws.recv()
ws.close()
```

### Available ROS Topics (199 total)

#### Battery and Power
- `/MC/battery_currents`
- `/MC/battery_percentage`
- `/MC/battery_voltage`
- `/MC/currents`

#### Navigation and Movement
- `/cmd_vel` - Velocity commands
- `/odom` - Odometry
- `/odom_enc` - Encoder odometry
- `/odom_imu1` - IMU 1 odometry
- `/odom_imu2` - IMU 2 odometry
- `/amcl_pose` - AMCL localization pose
- `/robot_pose` - Robot pose
- `/move_base/goal` - Navigation goal
- `/move_base/result` - Navigation result
- `/move_base/status` - Navigation status
- `/move_base_simple/goal` - Simple navigation goal

#### Sensors
- `/scan` - Laser scan
- `/f_scan` - Front scan
- `/b_scan` - Back scan
- `/f_raw_scan` - Front raw scan
- `/b_raw_scan` - Back raw scan
- `/imu_data` - IMU data
- `/ultrasonic_sensors/pointcloud_combined` - Ultrasonic sensors

#### Cameras
- `/camera_floor/driver/color/image_raw` - Floor camera color
- `/camera_floor/driver/depth/image_rect_raw` - Floor camera depth
- `/camera_floor/driver/infra1/image_rect_raw` - Floor camera IR1
- `/camera_floor/driver/infra2/image_rect_raw` - Floor camera IR2
- `/camera_top/background` - Top camera
- `/proximity/point_cloud` - Proximity sensors

#### Maps and Localization
- `/map` - Map data
- `/map_metadata` - Map metadata
- `/traffic_map` - Traffic map
- `/one_way_map` - One-way map
- `/localization_score` - Localization quality

#### Robot State
- `/robot_mode` - Robot mode
- `/robot_state` - Robot state
- `/robot_status` - Robot status
- `/safety_status` - Safety system status
- `/moving_state` - Moving state

#### Diagnostics
- `/diagnostics` - System diagnostics
- `/diagnostics_agg` - Aggregated diagnostics
- `/wifi_diagnostics` - WiFi diagnostics

#### Mission Control
- `/MissionController/prompt_user` - Mission prompts
- `/mirEventTrigger/events` - Event triggers
- `/mir_log` - MiR logs
- `/mir_status_msg` - Status messages

#### TF Transforms
- `/tf` - Dynamic transforms
- `/tf_static` - Static transforms

### Key Topics for Integration

#### Read-Only (Safe)
1. **Battery:** `/MC/battery_percentage`
2. **Position:** `/robot_pose` or `/amcl_pose`
3. **Status:** `/robot_status`
4. **Map:** `/map`
5. **Odometry:** `/odom`

#### Write (Requires Care)
1. **Velocity:** `/cmd_vel` - Direct velocity control
2. **Navigation:** `/move_base_simple/goal` - Send navigation goals
3. **Mission:** Via API REST (requires authentication)

## Integration Options

### Option 1: API REST (Recommended for Basic Control)
- ✅ Simple HTTP requests
- ✅ No ROS bridge required
- ✅ Works for status, battery, missions
- ⚠️ Requires authentication for some endpoints
- ⚠️ Limited real-time data

### Option 2: Rosbridge WebSocket (Recommended for Real-Time)
- ✅ Real-time data streaming
- ✅ Access to all ROS topics
- ✅ Can subscribe to sensors, odometry, etc.
- ⚠️ Requires ROS 1 to ROS 2 bridge
- ⚠️ More complex setup

### Option 3: Hybrid Approach (Best of Both)
- Use API REST for:
  - Status checks
  - Battery monitoring
  - Mission management
  - Map retrieval
- Use Rosbridge for:
  - Real-time position tracking
  - Sensor data streaming
  - Odometry visualization
  - Navigation feedback

## ROS 1 to ROS 2 Bridge

The MiR200 uses ROS 1 internally, while Kevin uses ROS 2. To integrate them, we need a bridge.

### Options

#### 1. mir_bridge (Native MiR Solution)
- MiR provides `mir_bridge` package
- Bridges specific topics between ROS 1 and ROS 2
- Pre-configured for MiR topics

#### 2. ros1_bridge (Generic Solution)
- Generic ROS 1 to ROS 2 bridge
- Can bridge any topic
- Requires manual configuration

#### 3. Custom Bridge
- Write custom bridge for specific topics
- More control over what gets bridged
- Can filter and transform data

### Recommended Topics to Bridge

#### Essential
- `/MC/battery_percentage` → Battery monitoring
- `/robot_pose` → Real-time position
- `/odom` → Odometry
- `/robot_status` → Robot state

#### Optional
- `/scan` → Laser scan visualization
- `/map` → Map display
- `/cmd_vel` → Velocity commands (if controlling from Kevin)

## Next Steps

### Phase 1: Basic Integration (Current)
- [x] Verify network connectivity
- [x] Test API REST endpoints
- [x] Test Rosbridge WebSocket connection
- [x] Obtain list of available ROS topics
- [ ] Create mir_ui module for MiR status display

### Phase 2: Real-Time Monitoring
- [ ] Set up ROS 1 to ROS 2 bridge
- [ ] Subscribe to battery topic
- [ ] Subscribe to position topic
- [ ] Display real-time data in mir_ui

### Phase 3: Control Integration
- [ ] Test sending navigation goals via Rosbridge
- [ ] Test sending velocity commands via Rosbridge
- [ ] Implement mission control via API REST
- [ ] Add safety checks and limits

### Phase 4: Advanced Features
- [ ] Map visualization in mir_ui
- [ ] Path planning visualization
- [ ] Multi-robot coordination
- [ ] Fleet management integration

## Security Notes

### Firewall
- MiR200 has firewall that blocks ICMP (ping)
- All service ports are accessible
- This is normal for industrial devices

### Authentication
- API REST requires authentication for some endpoints
- Rosbridge WebSocket does not require authentication
- Consider implementing authentication for production use

### Network Isolation
- MiR200 is on the same network as Kevin (192.168.1.0/24)
- Consider VLAN segmentation for production
- Implement firewall rules to restrict access

## Troubleshooting

### Cannot Ping MiR200
- **Cause:** Firewall blocks ICMP
- **Solution:** Use ARP or try connecting to services directly

### API REST Returns Authentication Error
- **Cause:** Endpoint requires authentication
- **Solution:** Use endpoints that don't require auth (like `/status`) or configure credentials

### WebSocket Connection Fails
- **Cause:** Network issue or service not running
- **Solution:** Verify port 9090 is open, check network connectivity

### ROS Topics Not Updating
- **Cause:** Robot is in Pause state
- **Solution:** Start robot mission or check robot state

## References

- [MiR REST API Documentation](https://www.mobile-industrial-robots.com/)
- [Rosbridge Protocol](https://github.com/RobotWebTools/rosbridge_suite)
- [ROS 1 to ROS 2 Migration Guide](https://docs.ros.org/en/rolling/Releases/Migration-Guide.html)

## Document History

- **2026-06-17:** Initial documentation created
  - Network connectivity verified
  - API REST tested
  - Rosbridge WebSocket tested
  - 199 ROS topics discovered
  - Integration plan created
