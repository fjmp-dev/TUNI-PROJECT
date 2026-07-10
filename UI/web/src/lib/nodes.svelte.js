// Shared poller for the node launcher: individual ROS nodes (/api/nodes) and whole
// containers (/api/containers). Ref-counted so multiple panels share one interval.
import { api } from './api.js';

export const nodesState = $state({ nodes: [], containers: [], system: [] });

let timer = null;
let refs = 0;
const POLL_MS = 4000;

async function tick() {
  try {
    const [n, c, s] = await Promise.all([api.listNodes(), api.listContainers(), api.listSystem()]);
    if (n?.nodes) nodesState.nodes = n.nodes;
    if (c?.services) nodesState.containers = c.services;
    if (s?.system) nodesState.system = s.system;
  } catch {
    /* keep last good values */
  }
}

export function refreshNodes() {
  return tick();
}

export function startNodes() {
  refs++;
  if (refs === 1) {
    tick();
    timer = setInterval(tick, POLL_MS);
  }
}

export function stopNodes() {
  refs = Math.max(0, refs - 1);
  if (refs === 0 && timer) {
    clearInterval(timer);
    timer = null;
  }
}
