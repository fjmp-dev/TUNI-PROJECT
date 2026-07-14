// Shared /api/ur/joints poller. A single interval feeds both the UR panel and the
// 3D viewer (ref-counted), so they don't each poll the backend.
import { api } from './api.js';
import { config } from './config.js';

export const jointsState = $state({ data: null });

let timer = null;
let refs = 0;

async function tick() {
  try {
    const r = await api.urJoints();
    // The backend answers 200 {available:false} when the UR driver simply is not running
    // (a normal state, not a fault). Anything else is real joint data.
    jointsState.data = r && r.available === false ? null : r;
  } catch {
    jointsState.data = null;
  }
}

export function startJoints() {
  refs++;
  if (refs === 1) {
    tick();
    timer = setInterval(tick, config.poll.urJointsMs);
  }
}

export function stopJoints() {
  refs = Math.max(0, refs - 1);
  if (refs === 0 && timer) {
    clearInterval(timer);
    timer = null;
  }
}
