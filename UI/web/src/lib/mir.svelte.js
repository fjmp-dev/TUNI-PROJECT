// Shared /api/mir/status poller. Ref-counted so the MiR panel and the Overview tile
// share ONE poll instead of two independent ones (Overview used a hardcoded 5 s poll,
// MirPanel a 4 s setTimeout chain — two implementations of the same request).
//
// It is a setTimeout CHAIN (not setInterval) so it can back off when the MiR is
// unreachable (usually powered off) instead of hammering the backend. The ref count
// doubles as the `dead` guard: once refs hit 0, schedule() refuses to re-arm, so an
// in-flight request that lands after the last consumer unmounts cannot revive the loop.
import { api } from './api.js';
import { config } from './config.js';

export const mirState = $state({ data: null, offline: false, failCount: 0 });

let timer = null;
let refs = 0;

async function tick() {
  try {
    const r = await api.mirStatus();
    // 200 {available:false} = powered off, which is a state, not a failure.
    if (r && r.available === false) {
      mirState.data = null;
      mirState.offline = true;
      mirState.failCount++;
    } else {
      mirState.data = r;
      mirState.offline = false;
      mirState.failCount = 0;
    }
  } catch {
    mirState.offline = true;
    mirState.failCount++;
  } finally {
    schedule();
  }
}

function schedule() {
  clearTimeout(timer);
  if (refs === 0) return; // no consumers left: do not re-arm (kills in-flight re-arm)
  const base = config.poll.mirStatusMs;
  const delay = mirState.offline
    ? Math.min(base * Math.min(mirState.failCount, 8), 30000)
    : base;
  timer = setTimeout(tick, delay);
}

export function startMir() {
  refs++;
  if (refs === 1) tick();
}

export function stopMir() {
  refs = Math.max(0, refs - 1);
  if (refs === 0) clearTimeout(timer);
}

// Manual "Refresh": clear the offline backoff and poll now.
export function refreshMir() {
  mirState.failCount = 0;
  clearTimeout(timer);
  tick();
}
