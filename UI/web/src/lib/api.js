// Thin REST client for the FastAPI backend. Centralizes error handling and the
// optional auth token so components never build fetch calls by hand.
import { config } from './config.js';

async function request(path, { method = 'GET', body } = {}) {
  const headers = {};
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  const token = config.token;
  if (token) headers['X-MIR-Token'] = token;

  const res = await fetch(config.apiBase + path, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  // Token expired/invalid (or auth turned on): drop it and return to the login
  // screen. /api/login itself surfaces its 401 to the caller instead.
  if (res.status === 401 && path !== '/api/login') {
    try {
      localStorage.removeItem('mir_token');
    } catch {
      /* ignore */
    }
    location.reload();
    return;
  }

  let data = null;
  try {
    data = await res.json();
  } catch {
    /* non-JSON response */
  }
  if (!res.ok) {
    const detail = (data && (data.detail || data.error)) || res.statusText;
    throw new Error(`HTTP ${res.status}: ${detail}`);
  }
  return data;
}

export const api = {
  login: (username, password) =>
    request('/api/login', { method: 'POST', body: { username, password } }),
  logout: () => request('/api/logout', { method: 'POST' }),

  // Profiles (multi-user)
  me: () => request('/api/me'),
  saveMyConfig: (nodes, settings) =>
    request('/api/me/config', { method: 'PUT', body: { nodes, settings } }),
  applyNodes: () => request('/api/me/apply', { method: 'POST' }),
  listUsers: () => request('/api/users'),
  createUser: (username, password, role, can_control = false) =>
    request('/api/users', { method: 'POST', body: { username, password, role, can_control } }),
  updateUser: (username, { role, password, can_control } = {}) =>
    request(`/api/users/${username}`, { method: 'PUT', body: { role, password, can_control } }),
  deleteUser: (username) =>
    request(`/api/users/${username}`, { method: 'DELETE' }),

  // Node launcher (individual nodes + whole containers) + read-only system status
  listNodes: () => request('/api/nodes'),
  listSystem: () => request('/api/system'),
  nodeStart: (id) => request(`/api/nodes/${id}/start`, { method: 'POST' }),
  nodeStop: (id) => request(`/api/nodes/${id}/stop`, { method: 'POST' }),
  nodeLogs: (id, lines = 200) => request(`/api/nodes/${id}/logs?lines=${lines}`),
  listContainers: () => request('/api/containers'),
  containerStart: (name) => request(`/api/containers/${name}/start`, { method: 'POST' }),
  containerStop: (name) => request(`/api/containers/${name}/stop`, { method: 'POST' }),

  // Nordbo force/torque sensors (our own WebSocket reader in the backend)
  force: () => request('/api/force'),
  forceTare: (side) => request(`/api/force/${side}/tare`, { method: 'POST' }),
  // Pause/resume the backend's Nordbo reader so the sensor's native web UI
  // (port 80, served by the sensor itself) can grab the single WebSocket slot
  // on :2003. Disconnect is reversible via forceConnect.
  forceDisconnect: (side) => request(`/api/force/${side}/disconnect`, { method: 'POST' }),
  forceConnect: (side) => request(`/api/force/${side}/connect`, { method: 'POST' }),

  mirStatus: () => request('/api/mir/status'),
  // Robot addresses, so the UI never hardcodes an IP a second time.
  suiteConfig: () => request('/api/config'),
  // Camera USB bus health + the one-click recovery when it falls off the bus.
  cameraUsb: () => request('/api/camera/usb'),
  cameraUsbReset: () => request('/api/camera/usb/reset', { method: 'POST' }),
  urStatus: () => request('/api/ur/status'),
  urJoints: () => request('/api/ur/joints'),
  urStart: () => request('/api/ur/start', { method: 'POST' }),
  urStop: () => request('/api/ur/stop', { method: 'POST' }),
  urMove: (arm, joint, delta) =>
    request('/api/ur/move', { method: 'POST', body: { arm, joint, delta } }),
  urPayload: (arm, mass, cog_x, cog_y, cog_z) =>
    request('/api/ur/payload', { method: 'POST', body: { arm, mass, cog_x, cog_y, cog_z } }),
  urFreedrive: (arm, enable) =>
    request('/api/ur/freedrive', { method: 'POST', body: { arm, enable } }),
};
