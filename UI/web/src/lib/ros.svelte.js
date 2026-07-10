// rosbridge connection manager. Exposes a reactive `connected` flag and the
// shared ROSLIB.Ros instance so panels (camera, joints) can subscribe to topics.
import ROSLIB from 'roslib';
import { config } from './config.js';
import { log } from './log.svelte.js';

export const rosState = $state({ connected: false });

let ros = null;
let retries = 0;
const MAX_RETRIES = 5;

export function getRos() {
  return ros;
}

export function connectRos() {
  retries = 0;
  _connect();
}

function _connect() {
  ros = new ROSLIB.Ros({ url: config.rosbridgeUrl });

  ros.on('connection', () => {
    retries = 0;
    rosState.connected = true;
    log('Connected to rosbridge', 'success');
  });
  ros.on('error', () => {
    rosState.connected = false;
  });
  ros.on('close', () => {
    rosState.connected = false;
    retries++;
    if (retries <= MAX_RETRIES) {
      log(`rosbridge disconnected, retry ${retries}/${MAX_RETRIES} in 5s…`, 'warn');
      setTimeout(_connect, 5000);
    } else {
      log('rosbridge unavailable after 5 retries — giving up', 'error');
    }
  });

  return ros;
}
