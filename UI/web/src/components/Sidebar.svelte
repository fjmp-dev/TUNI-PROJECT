<script>
  import { onMount, onDestroy } from 'svelte';
  import { api } from '../lib/api.js';
  import { log } from '../lib/log.svelte.js';
  import { nodesState, startNodes, stopNodes, refreshNodes } from '../lib/nodes.svelte.js';
  import { profile, isNodeSelected, toggleNode, saveMyConfig, canControl } from '../lib/profiles.svelte.js';

  // Collapse state is remembered per user (lightweight, in localStorage).
  const keyFor = () => `mir_sidebar_${profile.username || 'anon'}`;
  function loadCollapsed() {
    try { return localStorage.getItem(keyFor()) === '1'; } catch { return false; }
  }
  let collapsed = $state(loadCollapsed());
  function toggleCollapsed() {
    collapsed = !collapsed;
    try { localStorage.setItem(keyFor(), collapsed ? '1' : '0'); } catch {}
  }

  let busy = $state({}); // key -> bool

  // Monochrome monograms (theme is "no emojis"); fall back to first 2 letters.
  // Keep these in sync with the backend NODES / SYSTEM registries in main.py.
  const NODE_MONO = {
    ur_driver: 'UR', touch_real: 'TR', touch_mock: 'TM', hand_real: 'HR',
    hand_mock: 'HM', rosbag: 'RG', camera_color: 'CC', camera_depth: 'CD',
  };
  const CONT_MONO = { mir_ui: 'UI', mir_mir: 'MR', mir_camera: 'CM', mir_ur_driver: 'UR', mir_ur_driver_sim: 'US' };
  const SYS_MONO = { rosbridge: 'RB', joint_server: 'JS', action_bridge: 'AB', mir_bridge: 'MB' };
  const mono = (id, map) => map[id] || id.replace(/[^a-z]/gi, '').slice(0, 2).toUpperCase();

  // The two camera variants share the single USB device, so only one can run.
  // Block starting one while the other is up (the backend enforces one-at-a-time;
  // this just makes the constraint visible instead of a confusing error).
  function cameraConflict(id) {
    if (id !== 'camera_color' && id !== 'camera_depth') return false;
    const other = id === 'camera_color' ? 'camera_depth' : 'camera_color';
    const o = nodesState.nodes.find((x) => x.id === other);
    return !!(o && o.running);
  }

  async function withBusy(key, fn) {
    busy = { ...busy, [key]: true };
    try { await fn(); }
    finally { busy = { ...busy, [key]: false }; await refreshNodes(); }
  }

  const startNode = (id) => withBusy('n:' + id, async () => {
    log(`Starting node ${id}…`, 'info');
    try { await api.nodeStart(id); log(`${id} launching`, 'success'); }
    catch (e) { log(`${id}: ${e.message}`, 'error'); }
  });
  const stopNode = (id) => withBusy('n:' + id, async () => {
    log(`Stopping node ${id}…`, 'info');
    try { await api.nodeStop(id); log(`${id} stopped`, 'success'); }
    catch (e) { log(`${id}: ${e.message}`, 'error'); }
  });
  const startContainer = (name) => withBusy('c:' + name, async () => {
    log(`Starting container ${name}…`, 'info');
    try { await api.containerStart(name); log(`${name} started`, 'success'); }
    catch (e) { log(`${name}: ${e.message}`, 'error'); }
  });
  const stopContainer = (name) => withBusy('c:' + name, async () => {
    log(`Stopping container ${name}…`, 'info');
    try { await api.containerStop(name); log(`${name} stopped`, 'success'); }
    catch (e) { log(`${name}: ${e.message}`, 'error'); }
  });

  async function startMyNodes() {
    log('Starting your profile nodes…', 'info');
    try {
      const r = await api.applyNodes();
      log(`Started: ${(r.started || []).join(', ') || 'none'}`, 'success');
      if (r.errors?.length) log(`Errors: ${r.errors.map((e) => e.node).join(', ')}`, 'error');
    } catch (e) { log(`Apply failed: ${e.message}`, 'error'); }
    await refreshNodes();
  }

  async function saveConfig() {
    try { await saveMyConfig(); log(`Saved your config (${profile.config.nodes.length} nodes)`, 'success'); }
    catch (e) { log(`Save failed: ${e.message}`, 'error'); }
  }

  // Per-node log viewer (popup, auto-refreshing while open).
  let logNode = $state(null);
  let logLabel = $state('');
  let logText = $state('');
  let logTimer = null;
  async function refreshLog() {
    if (!logNode) return;
    try {
      const r = await api.nodeLogs(logNode);
      logText = (r.text && r.text.trim()) || '(no output yet)';
    } catch (e) {
      logText = 'error: ' + e.message;
    }
  }
  function openLogs(id, label) {
    logNode = id; logLabel = label; logText = 'loading…';
    refreshLog();
    clearInterval(logTimer);
    logTimer = setInterval(refreshLog, 1500);
  }
  function closeLogs() {
    logNode = null;
    clearInterval(logTimer);
    logTimer = null;
  }

  onMount(startNodes);
  onDestroy(() => { stopNodes(); clearInterval(logTimer); });
</script>

<aside class="sidebar" class:collapsed>
  <div class="side-head">
    {#if !collapsed}<span class="side-title">Nodes</span>{/if}
    <button class="collapse-btn" onclick={toggleCollapsed} title={collapsed ? 'Expand' : 'Collapse'}>
      {collapsed ? '»' : '«'}
    </button>
  </div>

  <div class="side-scroll">
    {#if !collapsed}<div class="side-section">Individual nodes</div>{/if}
    {#each nodesState.nodes as n (n.id)}
      <div class="item" title={collapsed ? `${n.label} — ${n.running ? 'running' : 'stopped'}` : ''}>
        <span class="mono">{mono(n.id, NODE_MONO)}</span>
        <span class="dot" class:on={n.running}></span>
        {#if !collapsed}
          <div class="meta"><div class="nm">{n.label}</div><div class="sub">{n.id}</div></div>
          <label class="pick" title="Include in my profile">
            <input type="checkbox" checked={isNodeSelected(n.id)} onchange={() => toggleNode(n.id)} />
          </label>
          <button class="mini logbtn" onclick={() => openLogs(n.id, n.label)} title="View logs">≡</button>
          {#if n.running}
            <button class="mini btn-danger" onclick={() => stopNode(n.id)} disabled={busy['n:' + n.id] || !canControl()} title={canControl() ? 'Stop' : 'Read-only: control not allowed'}>Stop</button>
          {:else}
            <button class="mini btn-accent" onclick={() => startNode(n.id)} disabled={busy['n:' + n.id] || !canControl() || cameraConflict(n.id)} title={!canControl() ? 'Read-only: control not allowed' : cameraConflict(n.id) ? 'Camera busy — stop the other variant first' : 'Start'}>Start</button>
          {/if}
        {/if}
      </div>
    {/each}

    {#if !collapsed}<div class="side-section">Containers</div>{/if}
    {#each nodesState.containers as c (c.name)}
      {@const mirOffline = c.name === 'mir_mir' && c.running && c.mir_reachable === false}
      <div class="item" title={collapsed ? `${c.label} — ${c.status}` : ''}>
        <span class="mono">{mono(c.name, CONT_MONO)}</span>
        <span class="dot" class:on={c.running && !mirOffline}></span>
        {#if !collapsed}
          <div class="meta">
            <div class="nm">{c.label}</div>
            <div class="sub">{mirOffline ? 'MiR offline' : c.status}</div>
          </div>
          <span class="pick"></span>
          {#if c.running}
            <button class="mini btn-danger" onclick={() => stopContainer(c.name)} disabled={busy['c:' + c.name] || c.name === 'mir_ui' || !canControl()} title={!canControl() ? 'Read-only: control not allowed' : c.name === 'mir_ui' ? 'Cannot stop the UI' : 'Stop'}>Stop</button>
          {:else}
            <button class="mini btn-accent" onclick={() => startContainer(c.name)} disabled={busy['c:' + c.name] || !c.exists || !canControl()} title={!canControl() ? 'Read-only: control not allowed' : !c.exists ? 'Not created — run docker compose up' : 'Start'}>Start</button>
          {/if}
        {/if}
      </div>
    {/each}

    {#if !collapsed}<div class="side-section">System (read-only)</div>{/if}
    {#each nodesState.system as s (s.id)}
      <div class="item sys" title={collapsed ? `${s.label} — ${s.running ? 'up' : 'down'}` : ''}>
        <span class="mono">{SYS_MONO[s.id] || mono(s.id, {})}</span>
        <span class="dot" class:on={s.running}></span>
        {#if !collapsed}
          <div class="meta"><div class="nm">{s.label}</div></div>
          <span class="state">{s.running ? 'up' : 'down'}</span>
        {/if}
      </div>
    {/each}

    {#if !collapsed}
      <div class="side-actions">
        <div class="side-section myp">My profile</div>
        <button class="wbtn btn-accent" onclick={startMyNodes} disabled={!canControl()}
                title={canControl() ? '' : 'Read-only: control not allowed'}>Start my nodes</button>
        <button class="wbtn" onclick={saveConfig}>Save my config</button>
        <div class="hint">
          Tick the <strong>☑</strong> next to the nodes you want, then <strong>Save my config</strong>.
          They auto-start when you log in — or press <strong>Start my nodes</strong> to launch them now.
        </div>
        {#if !canControl()}
          <div class="hint ro">You're read-only: you can pick &amp; save nodes, but starting them needs an admin to grant "Can control".</div>
        {/if}
      </div>
    {/if}
  </div>
</aside>

{#if logNode}
  <div class="log-overlay" onclick={closeLogs}>
    <div class="log-modal" onclick={(e) => e.stopPropagation()}>
      <div class="log-head">
        <span class="log-title">Logs — {logLabel} <span class="log-id">({logNode})</span></span>
        <div class="log-head-r">
          <span class="log-live">live</span>
          <button class="log-close" onclick={closeLogs} title="Close">✕</button>
        </div>
      </div>
      <pre class="log-body">{logText}</pre>
    </div>
  </div>
{/if}

<style>
  .sidebar {
    width: 250px; flex: none; align-self: stretch;
    background: var(--panel); border-right: 1px solid var(--border);
    display: flex; flex-direction: column;
    transition: width 0.15s ease;
  }
  .sidebar.collapsed { width: 56px; }

  .side-head {
    display: flex; align-items: center; justify-content: space-between;
    padding: 12px; border-bottom: 1px solid var(--border);
  }
  .side-title { font-size: 13px; font-weight: 600; color: #fff; text-transform: uppercase; letter-spacing: 0.05em; }
  .collapse-btn { padding: 2px 9px; font-size: 14px; line-height: 1; background: transparent; }
  .sidebar.collapsed .side-head { justify-content: center; }

  .side-scroll { flex: 1; overflow-y: auto; padding: 8px 6px; }
  .side-section {
    font-size: 10px; text-transform: uppercase; letter-spacing: 0.05em;
    color: var(--muted); margin: 10px 6px 5px;
  }
  .item {
    display: flex; align-items: center; gap: 8px;
    padding: 7px 6px; border-radius: 6px; margin-bottom: 3px;
  }
  .item:hover { background: rgba(255,255,255,0.04); }
  .sidebar.collapsed .item { justify-content: center; gap: 5px; padding: 7px 4px; }

  .mono {
    flex: none; width: 26px; height: 20px; border-radius: 4px;
    display: flex; align-items: center; justify-content: center;
    font-size: 10px; font-weight: 700; letter-spacing: 0.02em;
    color: var(--muted); background: var(--panel-2); border: 1px solid var(--border);
  }
  .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--err); flex: none; }
  .dot.on { background: var(--ok); box-shadow: 0 0 6px var(--ok); }
  .meta { flex: 1; min-width: 0; }
  .nm { font-size: 12px; color: #fff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .sub { font-size: 10px; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .pick { width: 16px; display: flex; align-items: center; justify-content: center; flex: none; }
  .pick input { width: 14px; height: 14px; cursor: pointer; }
  .mini { flex: none; padding: 3px 8px; font-size: 11px; line-height: 1.2; }
  .state { flex: none; font-size: 10px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.03em; }
  .logbtn { padding: 3px 7px; font-size: 12px; line-height: 1; }

  .log-overlay {
    position: fixed; inset: 0; background: rgba(0,0,0,0.6); z-index: 60;
    display: flex; align-items: center; justify-content: center; padding: 24px;
  }
  .log-modal {
    background: var(--panel); border: 1px solid var(--border); border-radius: 10px;
    width: min(900px, 92vw); height: min(70vh, 620px); display: flex; flex-direction: column; overflow: hidden;
  }
  .log-head {
    display: flex; align-items: center; justify-content: space-between;
    padding: 10px 14px; background: var(--panel-2); border-bottom: 1px solid var(--border);
  }
  .log-title { font-size: 13px; color: #fff; font-weight: 600; }
  .log-id { color: var(--muted); font-weight: 400; font-size: 11px; }
  .log-head-r { display: flex; align-items: center; gap: 10px; }
  .log-live { font-size: 10px; color: var(--ok); text-transform: uppercase; letter-spacing: 0.05em; }
  .log-close { padding: 2px 9px; background: transparent; }
  .log-body {
    flex: 1; margin: 0; padding: 12px 14px; overflow: auto;
    font-family: var(--mono); font-size: 12px; line-height: 1.45; color: var(--text);
    white-space: pre-wrap; word-break: break-word; background: #0b0e14;
  }

  .side-actions {
    padding: 10px 6px; margin: 8px 0;
    border-top: 1px solid var(--border); border-bottom: 1px solid var(--border);
    display: flex; flex-direction: column; gap: 8px;
  }
  .wbtn { width: 100%; padding: 7px 0; font-size: 12px; }
  .wbtn:disabled { opacity: 0.45; cursor: not-allowed; }
  .side-section.myp { margin: 0 0 2px; }
  .hint { font-size: 10px; color: var(--muted); line-height: 1.4; }
  .hint.ro { color: #e0a44e; }

  @media (max-width: 900px) {
    .sidebar { width: 210px; }
    .sidebar.collapsed { width: 52px; }
  }
</style>
