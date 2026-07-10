<script>
  import { onMount, onDestroy } from 'svelte';
  import { Terminal } from '@xterm/xterm';
  import { FitAddon } from '@xterm/addon-fit';
  import '@xterm/xterm/css/xterm.css';
  import { config } from '../lib/config.js';
  import { api } from '../lib/api.js';

  // Containers allowed for shell access (mirrors TERM_ALLOWED in main.py).
  const TERM_WHITELIST = ['mir_ur_driver', 'mir_ur_driver_sim', 'mir_mir', 'mir_camera'];

  let sel = $state('');           // selected container name
  let connected = $state(false);
  let containers = $state([]);    // running containers from /api/containers
  let termEl;
  let term, fit, ws, ro;

  async function loadContainers() {
    try {
      const r = await api.listContainers();
      const svcs = r?.services || [];
      containers = svcs.filter(
        (c) => TERM_WHITELIST.includes(c.name) && c.running
      );
      if (!sel && containers.length > 0) sel = containers[0].name;
    } catch { /* keep static label */ }
  }

  function containerLabel(name) {
    const c = containers.find((x) => x.name === name);
    return c?.label || name;
  }

  function wsUrl() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const params = new URLSearchParams();
    params.set('token', config.token || '');
    if (sel) params.set('container', sel);
    return `${proto}://${location.host}/api/term?${params.toString()}`;
  }

  function sendResize() {
    if (ws && ws.readyState === WebSocket.OPEN && term) {
      ws.send(JSON.stringify({ type: 'resize', cols: term.cols, rows: term.rows }));
    }
  }

  function connect() {
    if (!sel) return;
    if (ws) {
      try { ws.close(); } catch {}
      ws = null;
    }
    if (term) term.reset();
    
    // Add connection timeout
    const timeoutId = setTimeout(() => {
      if (ws && ws.readyState === WebSocket.CONNECTING) {
        ws.close();
        term.write('\r\n\x1b[31m[connection timeout - container may be busy]\x1b[0m\r\n');
      }
    }, 10000); // 10 second timeout
    
    ws = new WebSocket(wsUrl());
    ws.binaryType = 'arraybuffer';
    ws.onopen = () => {
      clearTimeout(timeoutId);
      connected = true;
      try { fit?.fit(); } catch {}
      sendResize();
    };
    ws.onmessage = (e) => {
      if (typeof e.data === 'string') term.write(e.data);
      else term.write(new Uint8Array(e.data));
    };
    ws.onclose = (e) => {
      clearTimeout(timeoutId);
      connected = false;
      if (e.code === 4401) term.write('\r\n\x1b[31m[unauthorized — admin only]\x1b[0m\r\n');
      else if (e.code === 4404) term.write('\r\n\x1b[31m[container not allowed]\x1b[0m\r\n');
      else if (e.code !== 1000) term.write('\r\n\x1b[33m[disconnected]\x1b[0m\r\n');
    };
    ws.onerror = () => { 
      clearTimeout(timeoutId);
      connected = false; 
    };
  }

  onMount(async () => {
    await loadContainers();
    term = new Terminal({
      cursorBlink: true,
      fontSize: 13,
      fontFamily: 'ui-monospace, Menlo, Consolas, monospace',
      theme: { background: '#0b0e14', foreground: '#d6deeb' },
    });
    fit = new FitAddon();
    term.loadAddon(fit);
    term.open(termEl);
    try { fit.fit(); } catch {}
    term.onData((d) => {
      if (ws && ws.readyState === WebSocket.OPEN) ws.send(new TextEncoder().encode(d));
    });
    ro = new ResizeObserver(() => {
      try { fit.fit(); } catch {}
      sendResize();
    });
    ro.observe(termEl);
    if (sel) connect();
  });

  onDestroy(() => {
    ro?.disconnect();
    try { ws?.close(); } catch {}
    term?.dispose();
  });
</script>

<div class="panel">
  <div class="panel-header">
    <h2>Terminal</h2>
    <div class="hdr-right">
      {#if containers.length > 0}
        <select bind:value={sel} onchange={connect}>
          {#each containers as c (c.name)}
            <option value={c.name}>{c.label}</option>
          {/each}
        </select>
      {:else}
        <span class="hint">no containers</span>
      {/if}
      <span class="badge {connected ? 'ok' : ''}">{connected ? 'connected' : 'closed'}</span>
      <button onclick={connect} disabled={!sel}>Connect</button>
    </div>
  </div>
  <div class="panel-body">
    <div class="term" bind:this={termEl}></div>
    {#if containers.length === 0}
      <div class="legend" style="color:var(--warn)">
        No shell-capable containers are running. Start <code>mir_camera</code> / <code>mir_mir</code> from the sidebar.
      </div>
    {:else}
      <div class="legend">Full shell inside the container (admin only). Try <code>ros2 node list</code>.</div>
    {/if}
  </div>
</div>

<style>
  .hdr-right { display: flex; align-items: center; gap: 8px; }
  .hdr-right select { font-size: 12px; padding: 4px 6px; }
  .term {
    height: 340px; background: #0b0e14; border-radius: 6px;
    padding: 6px; border: 1px solid var(--border); overflow: hidden;
  }
  .legend { margin-top: 10px; font-size: 11px; color: var(--muted); }
  .legend code { font-size: 10px; }
</style>
