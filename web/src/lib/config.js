// Central configuration for the MIR Suite web UI.
// REST goes to the same origin (FastAPI serves this build); rosbridge is on :9090.
const host = window.location.hostname;

export const config = {
  apiBase: '', // same-origin REST
  rosbridgeUrl: `ws://${host}:9090`,
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
