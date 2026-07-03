# ROUTER_MODEM — findings

## What it is
**Teltonika RUTX50** router (5G) that provides the network via SIM.
- **Router: `192.168.1.1`** (LAN gateway). Serial 6002231313, LAN MAC `20:97:27:31:D5:6F`.
- **Robot (Jetson): `192.168.1.75`** on `lan2`/`lan4`.
- The robot also has `lan1 = 195.148.48.186/24` → university network (TUNI), default gw `195.148.48.1`.
- Open ports: **22 (SSH/dropbear), 80, 443 (RutOS web)**.

## Access — RESOLVED (2026-07-02, via factory reset)
The router was locked (the sticker password had been changed on RutOS's first login).
Fixed with a factory reset (hold Reset button ~10 s).
- **Login:** `admin` / `Fastlab2026` (web `https://192.168.1.1` and API). SSH uses `root` with the same password.
- RMS (Teltonika cloud Remote Management System): Enabled but "Failure (Failed to resolve hostname)" → optional, Skip/Disable for the lab.

## WiFi (factory defaults)
- SSIDs `RUT_D571_2G` (2.4 GHz) and `RUT_D572_5G` (5 GHz — note the 5G one is D572), key `g9K2JeHu` (encryption psk2).
- **The MiR connects to `RUT_D571_2G` (2.4 GHz)** with a DHCP reservation → always `.13`, 0% packet loss (see [[mir-wifi-root-cause]]).

## SIM as WAN (Elisa) — CONNECTED
- MOB1S1A1 (SIM1), Quectel modem, dual-SIM. APN = **Auto**; the wired WAN is empty → internet comes over the SIM.
- After entering the SIM PIN, it registered: **Connected, Registered home, elisa, 5G (NSA)** ✅. IMSI 244052165708644 (Elisa FI), ICCID 89358021250508116490.
- ⚠️ **WEAK signal:** RSRP −128 dBm / RSSI −91 dBm (poor) → slow/unstable internet. Improve: properly attach the "Mobile" antennas + relocate the router (window, away from metal). Likely the same cause as the MiR's weak WiFi.
- SIM PIN is entered under Network → Mobile → SIM → PIN (only 3 attempts before the PUK).

## Static IP vs DHCP (2026-07)
The robot IPs are set on each device, not as DHCP reservations → a router reset does NOT lose them.
- **Jetson**: static confirmed (NetworkManager, method=manual).
- **UR arms** (.102/.103): respond; UR MACs (OUI 00:30:d6) captured. Static is configured on the pendant (Settings → Network); by design the ur_robot_driver uses static IPs.
- **MiR** (.13): confirmed by REST it is on **WiFi** (`wlp2s0`, MAC 34:41:5d:3e:55:f3). The static/dhcp flag is not exposed by REST v2.0.0 → see it in the MiR web UI (System → Settings → WiFi connection → IPv4).

## Addressing backup (to re-create reservations if needed after a reset)
| Device | IP | MAC |
|---|---|---|
| RUTX50 router | 192.168.1.1 | 20:97:27:31:d5:6f |
| Jetson (robot) | 192.168.1.75 | (static on the device, NetworkManager) |
| MiR200 | 192.168.1.13 | 34:41:5d:3e:55:f3 |
| UR left arm | 192.168.1.102 | 00:30:d6:3b:1e:75 |
| UR right arm | 192.168.1.103 | 00:30:d6:3b:1f:5f |

LAN gateway 192.168.1.1 · DNS 8.8.8.8/8.8.4.4. With this table you can re-create DHCP
reservations by MAC after a reset, or set a static IP on each device.
