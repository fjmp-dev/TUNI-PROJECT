<script>
  import { onMount } from 'svelte';
  import { connectRos } from './lib/ros.svelte.js';
  import Header from './components/Header.svelte';
  import CameraPanel from './components/CameraPanel.svelte';
  import MirPanel from './components/MirPanel.svelte';
  import UrPanel from './components/UrPanel.svelte';
  import Viewer3D from './components/Viewer3D.svelte';
  import SkillsPanel from './components/SkillsPanel.svelte';
  import LogPanel from './components/LogPanel.svelte';

  onMount(() => {
    connectRos();
  });
</script>

<Header />
<main class="grid">
  <CameraPanel />
  <Viewer3D />
  <MirPanel />
  <UrPanel />
  <div class="full"><SkillsPanel /></div>
  <div class="full"><LogPanel /></div>
</main>

<style>
  .grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    align-items: start;
    gap: 16px;
    padding: 16px;
    max-width: 1500px;
    margin: 0 auto;
  }
  .full { grid-column: 1 / -1; }
  @media (max-width: 1000px) {
    .grid { grid-template-columns: 1fr; }
  }
</style>
