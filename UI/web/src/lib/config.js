// Central configuration for the MIR Suite web UI.
// REST goes to the same origin (FastAPI serves this build); rosbridge is on :9090.
const host = window.location.hostname;

// rosbridge is reached SAME-ORIGIN through the Caddy proxy at /rosbridge, over http
// and over https alike (ws:// from an http page, wss:// from an https page — mixing
// them would be blocked as mixed content). rosbridge itself binds loopback only, so
// there is no ws://<host>:9090 to connect to from another machine any more.
// Exception: the Vite dev server (:5173) is not behind Caddy, so it talks to rosbridge
// directly — only works when the browser runs on the Jetson itself.
const _isDevServer = window.location.port === '5173';
const _wsScheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
const _rosbridgeUrl = _isDevServer
  ? `ws://${host}:9090`
  : `${_wsScheme}://${window.location.host}/rosbridge`;

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
