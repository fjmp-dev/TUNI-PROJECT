// Auth state. The token (issued by /api/login) lives in localStorage so it
// survives reloads; api.js reads it from there (config.token) for every request.
import { api } from './api.js';

function load() {
  try {
    return localStorage.getItem('mir_token') || '';
  } catch {
    return '';
  }
}

export const auth = $state({ token: load() });

export async function login(username, password) {
  const r = await api.login(username, password);
  try {
    localStorage.setItem('mir_token', r.token);
  } catch {
    /* ignore */
  }
  auth.token = r.token;
}

export function logout() {
  try {
    localStorage.removeItem('mir_token');
  } catch {
    /* ignore */
  }
  auth.token = '';
}
