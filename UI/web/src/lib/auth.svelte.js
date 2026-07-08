// Auth state. The token (issued by /api/login) lives in localStorage so it
// survives reloads; api.js reads it from there (config.token) for every request.
//
// CRITICAL INVARIANT: applyNodes() is called ONLY in login() (explicit user
// action), never in token restoration. This is so that reloading the page
// doesn't re-spawn the user's saved nodes (which may already be running, or
// have crashed, or simply be inappropriate to auto-restart). The sidebar has
// a "Start my nodes" button for manual retry. App.svelte uses api.me() to
// re-hydrate the profile on reload but never applyNodes.
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

// Tracks whether the current session already auto-applied nodes. Reset on
// logout. On a page reload the module re-initializes (so this resets to
// false), but the token still loads from localStorage in `load()` above —
// which is why App.svelte must NEVER call applyNodes on token-restore; only
// login() does, gated by this flag for defense in depth.
let _applied_this_session = false;

export async function login(username, password) {
  const r = await api.login(username, password);
  try {
    localStorage.setItem('mir_token', r.token);
  } catch {
    /* ignore */
  }
  auth.token = r.token;
  setProfile(r); // login returns { token, username, role, config }
  // Auto-start this profile's saved nodes — ONLY on explicit login, never
  // on reload. The flag protects against double-fire if login() is somehow
  // called twice (e.g. user mashes the button).
  if (!_applied_this_session) {
    _applied_this_session = true;
    api.applyNodes().catch(() => {});
  }
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
  _applied_this_session = false;
}
