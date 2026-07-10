// Current user's profile (multi-user auth). Hydrated from the /api/login response
// and /api/me. `config.nodes` is the set of nodes this user wants running; it is
// persisted server-side (a YAML per user) via saveMyConfig().
import { api } from './api.js';

export const profile = $state({
  username: '',
  role: '',
  can_control: false,
  config: { nodes: [], settings: {} },
});

export function setProfile(d) {
  if (!d) return;
  profile.username = d.username || '';
  profile.role = d.role || '';
  profile.can_control = !!d.can_control;
  profile.config = {
    nodes: d.config?.nodes ? [...d.config.nodes] : [],
    settings: d.config?.settings ? { ...d.config.settings } : {},
  };
}

export function clearProfile() {
  profile.username = '';
  profile.role = '';
  profile.can_control = false;
  profile.config = { nodes: [], settings: {} };
}

// True if the current user may actuate hardware. Mirrors the backend guard
// (_require_control): admins always may; a plain user needs can_control=true.
// The backend enforces this regardless — this is only for hiding/disabling UI.
export function canControl() {
  return profile.role === 'admin' || profile.can_control === true;
}

export function isNodeSelected(id) {
  return profile.config.nodes.includes(id);
}

export function toggleNode(id) {
  const nodes = profile.config.nodes;
  const i = nodes.indexOf(id);
  if (i >= 0) nodes.splice(i, 1);
  else nodes.push(id);
}

export async function saveMyConfig() {
  const r = await api.saveMyConfig(profile.config.nodes, profile.config.settings);
  setProfile(r);
  return r;
}
