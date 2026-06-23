<script>
  import { rosState } from '../lib/ros.svelte.js';
</script>

<header class="app-header">
  <div class="title">
    <h1>MIR Suite</h1>
    <span class="sub">Kevin · Jetson AGX Orin</span>
  </div>
  <div class="conn" title="Estado de rosbridge">
    <span class="dot" class:on={rosState.connected}></span>
    <span>{rosState.connected ? 'Conectado' : 'Desconectado'}</span>
  </div>
</header>

<style>
  .app-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 20px;
    background: var(--panel);
    border-bottom: 1px solid var(--border);
  }
  .title { display: flex; align-items: baseline; gap: 12px; }
  h1 { font-size: 18px; color: #fff; letter-spacing: 0.02em; }
  .sub { color: var(--muted); font-size: 12px; }
  .conn { display: flex; align-items: center; gap: 8px; color: var(--muted); font-size: 13px; }
  .dot { width: 9px; height: 9px; border-radius: 50%; background: var(--err); transition: background 0.2s; }
  .dot.on { background: var(--ok); }
</style>
