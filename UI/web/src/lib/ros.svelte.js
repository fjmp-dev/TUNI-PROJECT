// rosbridge connection manager. Exposes a reactive `connected` flag and the
// shared ROSLIB.Ros instance so panels (camera, joints) can subscribe to topics.
import ROSLIB from 'roslib';
import { config } from './config.js';
import { log } from './log.svelte.js';

export const rosState = $state({ connected: false });

let ros = null;

export function getRos() {
  return ros;
}

export function connectRos() {
  ros = new ROSLIB.Ros({ url: config.rosbridgeUrl });

  ros.on('connection', () => {
    rosState.connected = true;
    log('Connected to rosbridge', 'success');
  });
  ros.on('error', () => {
    rosState.connected = false;
  });
  ros.on('close', () => {
    rosState.connected = false;
    log('rosbridge disconnected, retrying in 5s…', 'error');
    setTimeout(connectRos, 5000);
  });

  return ros;
}
