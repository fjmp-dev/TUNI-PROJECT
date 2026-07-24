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
  let shellPassword = $state(''); // extra factor: the shell password (not the token)
  let showPwPrompt = $state(false); // password dialog opened by the Connect button
  let pwInput = $state('');          // value typed/pasted inside the dialog
  let pwShow = $state(false);        // reveal the password text in the dialog
  let pwField = $state();             // the dialog input element (for autofocus)

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
    // The token goes in the WebSocket subprotocol (see connect()), NOT here — a
    // query-string token leaks into proxy/access logs and browser history.
    if (sel) params.set('container', sel);
    return `${proto}://${location.host}/api/term?${params.toString()}`;
  }

  function sendResize() {
    if (ws && ws.readyState === WebSocket.OPEN && term) {
      ws.send(JSON.stringify({ type: 'resize', cols: term.cols, rows: term.rows }));
    }
  }

  function connect() {
    if (!sel || !shellPassword) return;
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
    
    // Token via subprotocol: ['mir-term', <token>]. The backend reads the 2nd value
    // and echoes 'mir-term' back on accept. Keeps the credential out of the URL.
    ws = new WebSocket(wsUrl(), ['mir-term', config.token || '']);
    ws.binaryType = 'arraybuffer';
    ws.onopen = () => {
      clearTimeout(timeoutId);
      // Send the shell password as the first message: the backend requires it
      // BEFORE opening the docker exec. Not in the URL, not in logs.
      ws.send(JSON.stringify({ type: 'auth', password: shellPassword }));
    };
    ws.onmessage = (e) => {
      if (typeof e.data === 'string') {
        // Once the backend confirms the shell password, we're fully connected.
        if (e.data.includes('[authenticated]')) {
          connected = true;
          try { fit?.fit(); } catch {}
          sendResize();
        }
        term.write(e.data);
      } else {
        term.write(new Uint8Array(e.data));
      }
    };
    ws.onclose = (e) => {
      clearTimeout(timeoutId);
      connected = false;
      if (e.code === 4401) term.write('\r\n\x1b[31m[unauthorized — admin only]\x1b[0m\r\n');
      else if (e.code === 4403) term.write('\r\n\x1b[31m[shell password incorrect]\x1b[0m\r\n');
      else if (e.code === 4404) term.write('\r\n\x1b[31m[container not allowed]\x1b[0m\r\n');
      else if (e.code === 4408) term.write('\r\n\x1b[31m[timeout waiting for shell password]\x1b[0m\r\n');
      else if (e.code !== 1000) term.write('\r\n\x1b[33m[disconnected]\x1b[0m\r\n');
    };
    ws.onerror = () => {
      clearTimeout(timeoutId);
      connected = false;
    };
  }

  // The Connect button opens this dialog instead of relying on a header field:
  // pasting into a plain modal input is reliable, and the shell only opens once
  // the password is confirmed here.
  function openPwPrompt() {
    if (!sel) return;
    pwInput = shellPassword || '';
    pwShow = false;
    showPwPrompt = true;
    // focus after the dialog renders
    setTimeout(() => pwField?.focus(), 0);
  }

  function cancelPwPrompt() {
    showPwPrompt = false;
    pwInput = '';
  }

  function submitPwPrompt() {
    if (!pwInput) return;
    shellPassword = pwInput;
    showPwPrompt = false;
    connect();
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
        <select bind:value={sel}>
          {#each containers as c (c.name)}
            <option value={c.name}>{c.label}</option>
          {/each}
        </select>
      {:else}
        <span class="hint">no containers</span>
      {/if}
      <span class="badge {connected ? 'ok' : ''}">{connected ? 'connected' : 'closed'}</span>
      <button onclick={openPwPrompt} disabled={!sel}>Connect</button>
    </div>
  </div>
  <div class="panel-body">
    <div class="term" bind:this={termEl}></div>
    {#if containers.length === 0}
      <div class="legend" style="color:var(--warn)">
        <!-- There has been no sidebar since the tabbed redesign; this told people to look
             at something that does not exist. Containers are started in the System tab. -->
        No shell-capable containers are running. Start <code>mir_camera</code> / <code>mir_mir</code> from the <strong>System</strong> tab.
      </div>
    {:else}
      <div class="legend">Full shell inside the container (admin only). Try <code>ros2 node list</code>.</div>
    {/if}
  </div>
</div>

{#if showPwPrompt}
  <!-- Password dialog: opened by Connect. A plain modal input pastes reliably,
       unlike the old header field. Enter submits, Escape cancels. -->
  <div
    class="pw-overlay"
    role="button"
    tabindex="-1"
    onclick={cancelPwPrompt}
    onkeydown={(e) => e.key === 'Escape' && cancelPwPrompt()}
  >
    <div
      class="pw-dialog"
      role="dialog"
      aria-modal="true"
      aria-label="Shell password"
      tabindex="-1"
      onclick={(e) => e.stopPropagation()}
      onkeydown={(e) => e.stopPropagation()}
    >
      <h3>Open shell — {containerLabel(sel)}</h3>
      <p class="pw-hint">Second factor: the shell password (not your login). Set in <code>config/.env</code>.</p>
      <div class="pw-row">
        <input
          bind:this={pwField}
          type={pwShow ? 'text' : 'password'}
          bind:value={pwInput}
          placeholder="shell password"
          autocomplete="off"
          onkeydown={(e) => { if (e.key === 'Enter') submitPwPrompt(); if (e.key === 'Escape') cancelPwPrompt(); }}
        />
        <button type="button" class="pw-toggle" onclick={() => (pwShow = !pwShow)}>
          {pwShow ? 'Hide' : 'Show'}
        </button>
      </div>
      <div class="pw-actions">
        <button type="button" class="pw-cancel" onclick={cancelPwPrompt}>Cancel</button>
        <button type="button" class="pw-open" onclick={submitPwPrompt} disabled={!pwInput}>Open shell</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .hdr-right { display: flex; align-items: center; gap: 8px; }
  .hdr-right select { font-size: 12px; padding: 4px 6px; }
  .term {
    height: 340px; background: #0b0e14; border-radius: 6px;
    padding: 6px; border: 1px solid var(--border); overflow: hidden;
  }
  .legend { margin-top: 10px; font-size: 11px; color: var(--muted); }
  .legend code { font-size: 10px; }

  .pw-overlay {
    position: fixed; inset: 0; z-index: 1000;
    background: rgba(0, 0, 0, 0.55);
    display: flex; align-items: center; justify-content: center;
  }
  .pw-dialog {
    background: var(--panel, #12151d);
    border: 1px solid var(--border, #2a2f3a);
    border-radius: 10px; padding: 18px 20px; width: min(92vw, 380px);
    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.5);
  }
  .pw-dialog h3 { margin: 0 0 4px; font-size: 15px; }
  .pw-hint { margin: 0 0 12px; font-size: 11px; color: var(--muted); }
  .pw-hint code { font-size: 10px; }
  .pw-row { display: flex; gap: 8px; }
  .pw-row input {
    flex: 1; font-size: 13px; padding: 7px 9px;
    border: 1px solid var(--border, #2a2f3a); border-radius: 6px;
    background: var(--bg, #0b0e14); color: inherit;
  }
  .pw-toggle {
    font-size: 11px; padding: 0 10px; border-radius: 6px;
    border: 1px solid var(--border, #2a2f3a); background: transparent; color: inherit;
    cursor: pointer;
  }
  .pw-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }
  .pw-actions button { font-size: 12px; padding: 7px 14px; border-radius: 6px; cursor: pointer; }
  .pw-cancel { border: 1px solid var(--border, #2a2f3a); background: transparent; color: inherit; }
  .pw-open { border: none; background: var(--accent, #3b82f6); color: #fff; }
  .pw-open:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
