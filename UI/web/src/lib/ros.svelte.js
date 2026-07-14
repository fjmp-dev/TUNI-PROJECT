// rosbridge connection manager. Exposes reactive connection state and the shared
// ROSLIB.Ros instance so panels (camera) can subscribe to topics.
//
// IT NEVER GIVES UP. The previous version retried 5 times, 5s apart, then stopped
// forever: after the mir_ur_driver container restarted (a Jetson reboot, a driver
// stop/start, an image rebuild -- all routine), an open tab burned its 25 seconds of
// retries and then displayed "offline" indefinitely, even with rosbridge healthy and
// reachable. Verified on 2026-07-14: rosbridge back up for a full minute, tab still
// "offline"; only F5 fixed it. A robot console must not lie about the state of the
// robot, and the operator must not have to know to press reload.
//
// `generation` increments on every new Ros instance. Subscribers MUST watch it and
// re-subscribe: a ROSLIB.Topic is bound to the Ros object it was created with, so
// after a reconnect every old Topic hangs off a dead socket and silently delivers
// nothing (this is why the camera stayed black after a reconnect).
import ROSLIB from 'roslib';
import { config } from './config.js';
import { log } from './log.svelte.js';

const INITIAL_DELAY = 2000;
const MAX_DELAY = 30000;

export const rosState = $state({
  connected: false,
  reconnecting: false,
  generation: 0,
});

let ros = null;
let timer = null;
let delay = INITIAL_DELAY;
let everConnected = false;

export function getRos() {
  return ros;
}

export function connectRos() {
  delay = INITIAL_DELAY;
  _connect();
}

function _schedule() {
  clearTimeout(timer);
  rosState.reconnecting = true;
  timer = setTimeout(_connect, delay);
  // Exponential backoff with a ceiling: a rebooting Jetson can take minutes, and
  // hammering the socket every 5 s for all of them helps nobody.
  delay = Math.min(delay * 2, MAX_DELAY);
}

function _connect() {
  clearTimeout(timer);
  ros = new ROSLIB.Ros({ url: config.rosbridgeUrl });
  rosState.generation++;

  ros.on('connection', () => {
    delay = INITIAL_DELAY;
    rosState.connected = true;
    rosState.reconnecting = false;
    log(everConnected ? 'Reconnected to rosbridge' : 'Connected to rosbridge', 'success');
    everConnected = true;
  });

  // roslib emits 'error' and then 'close' for a failed attempt, so only 'close'
  // schedules the retry -- otherwise one failure would queue two timers.
  ros.on('error', () => {
    rosState.connected = false;
  });

  ros.on('close', () => {
    const wasConnected = rosState.connected;
    rosState.connected = false;
    if (wasConnected) log('rosbridge disconnected — reconnecting…', 'warn');
    _schedule();
  });

  return ros;
}

// Retry immediately, instead of waiting out the backoff, when the situation
// obviously changed: the machine came back online, or the operator returned to the
// tab. Without this a tab left open overnight sits in the 30 s cycle and can look
// dead for half a minute after the robot is already back.
if (typeof window !== 'undefined') {
  const kick = () => {
    if (!rosState.connected && document.visibilityState === 'visible') {
      delay = INITIAL_DELAY;
      _connect();
    }
  };
  window.addEventListener('online', kick);
  document.addEventListener('visibilitychange', kick);
}
