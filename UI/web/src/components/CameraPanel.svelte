<script>
  import { onMount, onDestroy } from 'svelte';
  import ROSLIB from 'roslib';
  import { getRos, rosState } from '../lib/ros.svelte.js';
  import { config } from '../lib/config.js';
  import { api } from '../lib/api.js';
  import { canControl } from '../lib/profiles.svelte.js';

  let imgSrc = $state('');
  let fps = $state(0);
  let active = $state(true);
  let topic = null;
  let frames = 0;
  let fpsTimer;

  // The generation this `topic` was created against. A ROSLIB.Topic is bound to the
  // Ros object it was made with, so after a reconnect the old one hangs off a dead
  // socket and silently delivers nothing -- the feed would go black with the UI
  // still claiming "connected". Tracking the generation forces a fresh subscription.
  let topicGen = -1;

  function subscribe() {
    const ros = getRos();
    if (!ros) return;
    if (topic && topicGen === rosState.generation) return; // already live on this socket
    topic = null; // stale one (if any) died with its socket; nothing to unsubscribe
    topicGen = rosState.generation;
    topic = new ROSLIB.Topic({
      ros,
      name: config.topics.cameraImage,
      messageType: 'sensor_msgs/CompressedImage',
    });
    topic.subscribe((msg) => {
      imgSrc = 'data:image/jpeg;base64,' + msg.data;
      frames++;
    });
  }

  function unsubscribe() {
    if (topic) {
      topic.unsubscribe();
      topic = null;
    }
    topicGen = -1;
  }

  function toggle() {
    active = !active;
    if (active) subscribe();
    else {
      unsubscribe();
      imgSrc = '';
    }
  }

  // (Re)subscribe whenever rosbridge connects -- and on every new connection
  // generation, which is what makes the feed come back after a reconnect.
  $effect(() => {
    rosState.generation; // tracked: re-runs on reconnect
    if (rosState.connected && active) subscribe();
  });

  // ---- USB bus health ----
  // The camera drops off the USB bus while still plugged in: the node runs, the feed
  // stays black, and nothing in the UI explains why. The backend can see the bus (it
  // reads /sys), so ask it, and offer the one-click recovery instead of making someone
  // find a shell and a sudo password.
  let usbPresent = $state(true);
  let usbBusy = $state(false);
  let usbMsg = $state('');
  let usbTimer;

  async function pollUsb() {
    try { usbPresent = (await api.cameraUsb()).present; } catch { /* ignore */ }
  }

  async function resetUsb() {
    usbBusy = true;
    usbMsg = 'Power-cycling the USB hub…';
    try {
      const r = await api.cameraUsbReset();
      usbPresent = r.present;
      usbMsg = r.present
        ? 'Camera is back on the bus — start its node from the System tab.'
        : 'Still missing. Unplug the camera and plug it back in (USB 3 port).';
    } catch (e) {
      usbMsg = e.message;
    } finally {
      usbBusy = false;
    }
  }

  onMount(() => {
    fpsTimer = setInterval(() => {
      fps = frames;
      frames = 0;
    }, 1000);
    pollUsb();
    usbTimer = setInterval(pollUsb, 5000);
  });
  onDestroy(() => {
    clearInterval(fpsTimer);
    clearInterval(usbTimer);
    unsubscribe();
  });
</script>

<div class="panel">
  <div class="panel-header">
    <h2>Orbbec Camera</h2>
    <div class="hdr-right">
      <span class="badge" class:err={!usbPresent} title={usbPresent
              ? 'Camera is on the USB bus' : 'Camera is NOT on the USB bus'}>
        {usbPresent ? 'usb ok' : 'no usb'}
      </span>
      <span class="badge">{fps} FPS</span>
      <!-- Always reachable, not only when the fault is already visible: the feed can be
           black for several reasons and "did the camera fall off the bus again?" is the
           first thing anyone asks. Harmless when the camera is healthy -- the backend
           short-circuits and never cycles the hub. -->
      <button onclick={resetUsb} disabled={usbBusy || !canControl()}
              title={canControl()
                ? 'Power-cycle the camera’s USB 3 hub. Safe: the hands and keyboard are on another bus and are never touched.'
                : 'Read-only: control not allowed'}>
        {usbBusy ? 'Resetting…' : 'Reset USB'}
      </button>
      <button onclick={toggle}>{active ? 'Stop' : 'Start'}</button>
    </div>
  </div>
  <div class="panel-body">
    {#if !usbPresent}
      <div class="usb-alert">
        <div class="usb-txt">
          <strong>The camera is not on the USB bus.</strong>
          It is plugged in, but the kernel cannot see it — a known fault of this model.
          The feed stays black until its USB hub is power-cycled.
        </div>
        <button class="btn-accent" onclick={resetUsb} disabled={usbBusy || !canControl()}
                title={canControl() ? 'Power-cycle the camera’s USB 3 hub (the hands and keyboard are not touched)'
                                    : 'Read-only: control not allowed'}>
          {usbBusy ? 'Resetting…' : 'Reset USB'}
        </button>
      </div>
    {/if}
    {#if usbMsg}<div class="usb-msg">{usbMsg}</div>{/if}
    <div class="view">
      {#if imgSrc}
        <img src={imgSrc} alt="camera" />
      {:else}
        <div class="placeholder">{active ? 'Waiting for image…' : 'Stopped'}</div>
      {/if}
    </div>
  </div>
</div>

<style>
  .usb-alert {
    display: flex; align-items: center; gap: 14px; margin-bottom: 12px;
    padding: 11px 13px; border-radius: 9px; font-size: 12.5px; line-height: 1.5;
    background: var(--warn-soft); border: 1px solid color-mix(in srgb, var(--warn) 32%, transparent);
  }
  .usb-alert .usb-txt { flex: 1; min-width: 0; color: var(--text); }
  .usb-alert button { white-space: nowrap; }
  .usb-msg { margin-bottom: 12px; font-size: 12.5px; color: var(--muted); }
  .view {
    aspect-ratio: 16 / 10;
    background: #000;
    border-radius: 6px;
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  img { width: 100%; height: 100%; object-fit: contain; }
  .placeholder { color: var(--muted); font-size: 13px; }
  .hdr-right { display: flex; align-items: center; gap: 8px; }
</style>
