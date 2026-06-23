<script>
  import { onMount } from 'svelte';
  import { connectRos } from './lib/ros.svelte.js';
  import Header from './components/Header.svelte';
  import CameraPanel from './components/CameraPanel.svelte';
  import MirPanel from './components/MirPanel.svelte';
  import UrPanel from './components/UrPanel.svelte';
  import Viewer3D from './components/Viewer3D.svelte';
  import LogPanel from './components/LogPanel.svelte';

  onMount(() => {
    connectRos();
  });
</script>

<Header />
<main class="grid">
  <div class="col">
    <CameraPanel />
    <MirPanel />
  </div>
  <div class="col">
    <UrPanel />
    <Viewer3D />
  </div>
  <div class="full">
    <LogPanel />
  </div>
</main>

<style>
  .grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    padding: 16px;
    max-width: 1400px;
    margin: 0 auto;
  }
  .col { display: flex; flex-direction: column; gap: 16px; }
  .full { grid-column: 1 / -1; }
  @media (max-width: 900px) {
    .grid { grid-template-columns: 1fr; }
  }
</style>
