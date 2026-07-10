// Central configuration for the MIR Suite web UI.
// REST goes to the same origin (FastAPI serves this build); rosbridge is on :9090.
const host = window.location.hostname;

// Under TLS the page is served by the Caddy reverse proxy, which exposes rosbridge
// same-origin at wss://<host>/rosbridge (rosbridge itself stays plain-ws on loopback).
// Without TLS (dev / no proxy) connect directly to ws://<host>:9090. Using ws:// from
// an https page would be blocked as mixed content, hence the protocol switch.
const _rosbridgeUrl =
  window.location.protocol === 'https:'
    ? `wss://${window.location.host}/rosbridge`
    : `ws://${host}:9090`;

export const config = {
  apiBase: '', // same-origin REST
  rosbridgeUrl: _rosbridgeUrl,
  topics: {
    cameraImage: '/camera/color/image_raw/compressed',
    jointStates: '/joint_states',
  },
  poll: {
    mirStatusMs: 4000,
    urStatusMs: 5000,
    urJointsMs: 250,
  },
  // Optional bearer token for write endpoints (backend auth is opt-in and not
  // enabled yet; sending it early is harmless). Stored in localStorage.
  get token() {
    try {
      return localStorage.getItem('mir_token') || '';
    } catch {
      return '';
    }
  },
};
