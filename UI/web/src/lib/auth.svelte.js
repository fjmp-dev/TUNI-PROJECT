// Auth state. The token (issued by /api/login) lives in localStorage so it
// survives reloads; api.js reads it from there (config.token) for every request.
//
// CRITICAL INVARIANT: NOTHING is started as a side effect of logging in.
// Logging in used to call applyNodes(), which spawned every node saved in the
// profile. On 2026-07-13 that silently started `rosbag` (saved in admin's
// profile) on each login; it recorded every topic and wrote 522 GB, filling the
// disk. Even for harmless nodes it is the wrong default: opening a web page must
// not power things up on a robot. Nodes now start only when someone clicks them
// -- per node, or via the explicit "Start my nodes" button.
import { api } from './api.js';
import { setProfile, clearProfile } from './profiles.svelte.js';

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
  setProfile(r); // login returns { token, username, role, config }
  // Deliberately does NOT start anything. The profile's node list is a shortcut
  // ("Start my nodes"), not an autostart list.
}

export async function logout() {
  try {
    await api.logout();
  } catch {
    /* ignore */
  }
  try {
    localStorage.removeItem('mir_token');
  } catch {
    /* ignore */
  }
  auth.token = '';
  clearProfile();
}
