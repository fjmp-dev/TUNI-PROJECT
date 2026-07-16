// Shared /api/force poller. A single ref-counted interval feeds both the Arms-tab
// ForcePanel and the Overview tile, so the Nordbo endpoint is polled once regardless
// of how many components are mounted (previously ForcePanel polled every 150 ms AND
// Overview every 700 ms, independently — the biggest steady-state load in the UI).
import { api } from './api.js';
import { config } from './config.js';

export const forceState = $state({ sensors: { left: null, right: null } });

let timer = null;
let refs = 0;

async function tick() {
  try {
    const r = await api.force();
    if (r?.sensors) forceState.sensors = r.sensors;
  } catch {
    /* keep last good values */
  }
}

export function startForce() {
  refs++;
  if (refs === 1) {
    tick();
    timer = setInterval(tick, config.poll.forceMs);
  }
}

export function stopForce() {
  refs = Math.max(0, refs - 1);
  if (refs === 0 && timer) {
    clearInterval(timer);
    timer = null;
  }
}
