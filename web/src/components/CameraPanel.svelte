<script>
  import { onMount, onDestroy } from 'svelte';
  import ROSLIB from 'roslib';
  import { getRos, rosState } from '../lib/ros.svelte.js';
  import { config } from '../lib/config.js';

  let imgSrc = $state('');
  let fps = $state(0);
  let active = $state(true);
  let topic = null;
  let frames = 0;
  let fpsTimer;

  function subscribe() {
    const ros = getRos();
    if (!ros || topic) return;
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
  }

  function toggle() {
    active = !active;
    if (active) subscribe();
    else {
      unsubscribe();
      imgSrc = '';
    }
  }

  // (Re)subscribe whenever rosbridge connects while the feed is enabled.
  $effect(() => {
    if (rosState.connected && active) subscribe();
  });

  onMount(() => {
    fpsTimer = setInterval(() => {
      fps = frames;
      frames = 0;
    }, 1000);
  });
  onDestroy(() => {
    clearInterval(fpsTimer);
    unsubscribe();
  });
</script>

<div class="panel">
  <div class="panel-header">
    <h2>Cámara Orbbec</h2>
    <div class="hdr-right">
      <span class="badge">{fps} FPS</span>
      <button onclick={toggle}>{active ? 'Detener' : 'Iniciar'}</button>
    </div>
  </div>
  <div class="panel-body">
    <div class="view">
      {#if imgSrc}
        <img src={imgSrc} alt="cámara" />
      {:else}
        <div class="placeholder">{active ? 'Esperando imagen…' : 'Detenida'}</div>
      {/if}
    </div>
  </div>
</div>

<style>
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
