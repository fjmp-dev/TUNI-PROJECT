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
  mirStatus: () => request('/api/mir/status'),
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
