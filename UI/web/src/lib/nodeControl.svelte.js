// Shared control actions for nodes / containers, used by both Overview and the
// System view so behaviour (busy state, logging, refresh) stays consistent.
// The backend enforces the can_control permission regardless; the UI just
// disables the buttons for read-only users.
import { api } from './api.js';
import { log } from './log.svelte.js';
import { refreshNodes } from './nodes.svelte.js';

export const busy = $state({}); // key -> bool

async function withBusy(key, fn) {
  busy[key] = true;
  try { await fn(); }
  finally { busy[key] = false; await refreshNodes(); }
}

export const startNode = (id) => withBusy('n:' + id, async () => {
  log(`Starting node ${id}…`, 'info');
  try { await api.nodeStart(id); log(`${id} launching`, 'success'); }
  catch (e) { log(`${id}: ${e.message}`, 'error'); }
});
export const stopNode = (id) => withBusy('n:' + id, async () => {
  log(`Stopping node ${id}…`, 'info');
  try { await api.nodeStop(id); log(`${id} stopped`, 'success'); }
  catch (e) { log(`${id}: ${e.message}`, 'error'); }
});
export const startContainer = (name) => withBusy('c:' + name, async () => {
  log(`Starting container ${name}…`, 'info');
  try { await api.containerStart(name); log(`${name} started`, 'success'); }
  catch (e) { log(`${name}: ${e.message}`, 'error'); }
});
export const stopContainer = (name) => withBusy('c:' + name, async () => {
  log(`Stopping container ${name}…`, 'info');
  try { await api.containerStop(name); log(`${name} stopped`, 'success'); }
  catch (e) { log(`${name}: ${e.message}`, 'error'); }
});

export async function startMyNodes() {
  log('Starting your profile nodes…', 'info');
  try {
    const r = await api.applyNodes();
    log(`Started: ${(r.started || []).join(', ') || 'none'}`, 'success');
    if (r.errors?.length) log(`Errors: ${r.errors.map((e) => e.node).join(', ')}`, 'error');
  } catch (e) { log(`Apply failed: ${e.message}`, 'error'); }
  await refreshNodes();
}
