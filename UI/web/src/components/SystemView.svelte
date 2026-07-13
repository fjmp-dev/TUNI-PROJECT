<script>
  import { onMount, onDestroy } from 'svelte';
  import { api } from '../lib/api.js';
  import { log } from '../lib/log.svelte.js';
  import { nodesState, startNodes, stopNodes } from '../lib/nodes.svelte.js';
  import { profile, isNodeSelected, toggleNode, saveMyConfig, canControl } from '../lib/profiles.svelte.js';
  import { busy, startNode, stopNode, startContainer, stopContainer, startMyNodes } from '../lib/nodeControl.svelte.js';

  // The two camera variants share the single USB device, so only one can run.
  function cameraConflict(id) {
    if (id !== 'camera_color' && id !== 'camera_depth') return false;
    const other = id === 'camera_color' ? 'camera_depth' : 'camera_color';
    const o = nodesState.nodes.find((x) => x.id === other);
    return !!(o && o.running);
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
    try { const r = await api.nodeLogs(logNode); logText = (r.text && r.text.trim()) || '(no output yet)'; }
    catch (e) { logText = 'error: ' + e.message; }
  }
  function openLogs(id, label) {
    logNode = id; logLabel = label; logText = 'loading…';
    refreshLog(); clearInterval(logTimer); logTimer = setInterval(refreshLog, 1500);
  }
  function closeLogs() { logNode = null; clearInterval(logTimer); logTimer = null; }

  // "What does this do?" popup. Nothing here starts until someone clicks Start, so
  // the list is only useful if you can tell what each entry actually is.
  let info = $state(null); // { label, desc, running }
  const openInfo = (p) => (info = p);
  const closeInfo = () => (info = null);

  onMount(startNodes);
  onDestroy(() => { stopNodes(); clearInterval(logTimer); });
</script>

<div class="view-head">
  <div>
    <div class="eyebrow">Processes &amp; containers</div>
    <h1>System</h1>
    <p>Start and stop nodes and containers, tick the ones for your profile, and inspect logs.
       Control actions need the <em>can&nbsp;control</em> permission.</p>
  </div>
  <div class="head-actions">
    <button onclick={saveConfig}>Save my config</button>
    <button class="btn-accent" onclick={startMyNodes} disabled={!canControl()}
            title={canControl() ? 'Launch the nodes ticked in your profile' : 'Read-only: control not allowed'}>Start my nodes</button>
  </div>
</div>

{#if !canControl()}
  <div class="ro-note">You're <strong>read-only</strong>: you can pick &amp; save your nodes, but starting or stopping them needs an admin to grant “Can control”.</div>
{/if}

<div class="sys-grid">
  <!-- Nodes -->
  <div class="panel">
    <div class="panel-header">
      <h2>Nodes</h2>
      <span class="badge ok">{nodesState.nodes.filter((n) => n.running).length} running</span>
    </div>
    <div class="panel-body list">
      {#each nodesState.nodes as n (n.id)}
        <div class="row">
          <span class="pdot" class:on={n.running}></span>
          <label class="pick" title="Include in my profile">
            <input type="checkbox" checked={isNodeSelected(n.id)} onchange={() => toggleNode(n.id)} />
          </label>
          <span class="info"><span class="pname">{n.label}</span><span class="pid">{n.id}</span></span>
          <button class="ghost qmark" onclick={() => openInfo(n)} title="What does this do?" aria-label="What does {n.label} do?">?</button>
          <button class="ghost" onclick={() => openLogs(n.id, n.label)} title="View logs">logs</button>
          {#if n.running}
            <button class="btn-danger sm" onclick={() => stopNode(n.id)} disabled={busy['n:' + n.id] || !canControl()} title={canControl() ? 'Stop' : 'Read-only: control not allowed'}>Stop</button>
          {:else}
            <button class="btn-accent sm" onclick={() => startNode(n.id)} disabled={busy['n:' + n.id] || !canControl() || cameraConflict(n.id)}
                    title={!canControl() ? 'Read-only: control not allowed' : cameraConflict(n.id) ? 'Camera busy — stop the other variant first' : 'Start'}>Start</button>
          {/if}
        </div>
      {/each}
    </div>
  </div>

  <!-- Containers + system -->
  <div class="panel">
    <div class="panel-header">
      <h2>Containers &amp; system</h2>
      <span class="badge">{nodesState.containers.filter((c) => c.running).length}/{nodesState.containers.length} up</span>
    </div>
    <div class="panel-body list">
      {#each nodesState.containers as c (c.name)}
        {@const mirOffline = c.name === 'mir_mir' && c.running && c.mir_reachable === false}
        <div class="row">
          <span class="pdot" class:on={c.running && !mirOffline}></span>
          <span class="pick"></span>
          <span class="info"><span class="pname">{c.label}</span><span class="pid">{c.name}</span></span>
          <span class="cmeta">{mirOffline ? 'MiR offline' : c.status}</span>
          {#if c.running}
            <button class="btn-danger sm" onclick={() => stopContainer(c.name)} disabled={busy['c:' + c.name] || c.name === 'mir_ui' || !canControl()}
                    title={!canControl() ? 'Read-only: control not allowed' : c.name === 'mir_ui' ? 'Cannot stop the UI' : 'Stop'}>Stop</button>
          {:else}
            <button class="btn-accent sm" onclick={() => startContainer(c.name)} disabled={busy['c:' + c.name] || !c.exists || !canControl()}
                    title={!canControl() ? 'Read-only: control not allowed' : !c.exists ? 'Not created — run docker compose up' : 'Start'}>Start</button>
          {/if}
        </div>
      {/each}

      <div class="grouplabel">System (read-only)</div>
      {#each nodesState.system as s (s.id)}
        <div class="row sys">
          <span class="pdot" class:on={s.running}></span>
          <span class="pick"></span>
          <span class="info"><span class="pname">{s.label}</span></span>
          <button class="ghost qmark" onclick={() => openInfo(s)} title="What does this do?" aria-label="What does {s.label} do?">?</button>
          <span class="sys-state" class:up={s.running}>{s.running ? 'up' : 'down'}</span>
        </div>
      {/each}
    </div>
  </div>
</div>

<div class="profile-hint">
  Nothing starts on its own. Tick <strong>☑</strong> the nodes you use and <strong>Save my config</strong>; then
  <strong>Start my nodes</strong> launches that set in one click, whenever <em>you</em> ask for it.
  Not sure what something is? Hit <strong>?</strong> next to it.
</div>

{#if logNode}
  <div class="log-overlay" onclick={closeLogs}>
    <div class="log-modal" onclick={(e) => e.stopPropagation()}>
      <div class="log-head">
        <span class="log-title">Logs — {logLabel} <span class="log-id">({logNode})</span></span>
        <div class="log-head-r"><span class="log-live">live</span><button class="log-close" onclick={closeLogs} title="Close">✕</button></div>
      </div>
      <pre class="log-body">{logText}</pre>
    </div>
  </div>
{/if}

{#if info}
  <div class="log-overlay" onclick={closeInfo}>
    <div class="log-modal info-modal" onclick={(e) => e.stopPropagation()}>
      <div class="log-head">
        <span class="log-title">{info.label}{#if info.id}<span class="log-id">({info.id})</span>{/if}</span>
        <button class="log-close" onclick={closeInfo} title="Close">✕</button>
      </div>
      <div class="info-body">
        <p>{info.desc || 'No description yet.'}</p>
        <div class="info-meta">
          <span class="info-state" class:up={info.running}>{info.running ? 'running' : 'stopped'}</span>
          {#if info.container}<span class="info-chip">{info.container}</span>{/if}
          {#if info.no_autostart}<span class="info-chip warn">manual start only</span>{/if}
        </div>
      </div>
    </div>
  </div>
{/if}

<style>
  .qmark { font-weight: 700; width: 22px; text-align: center; }
  .info-modal { max-width: 460px; }
  .info-body { padding: 14px 16px 16px; }
  .info-body p { margin: 0 0 12px; font-size: 13.5px; line-height: 1.55; color: var(--text); }
  .info-meta { display: flex; gap: 6px; flex-wrap: wrap; }
  .info-state, .info-chip {
    font-family: var(--mono); font-size: 10.5px; font-weight: 600; padding: 2px 8px; border-radius: 20px;
    text-transform: uppercase; letter-spacing: 0.04em; color: var(--faint); background: var(--panel-3);
    border: 1px solid transparent;
  }
  .info-state.up { color: var(--ok); background: var(--ok-soft); border-color: color-mix(in srgb, var(--ok) 30%, transparent); }
  .info-chip.warn { color: var(--warn); background: var(--warn-soft); border-color: color-mix(in srgb, var(--warn) 30%, transparent); }
  .head-actions { display: flex; gap: 8px; }
  .ro-note {
    margin-bottom: 14px; padding: 10px 13px; border-radius: 9px; font-size: 12.5px;
    background: var(--warn-soft); border: 1px solid color-mix(in srgb, var(--warn) 30%, transparent); color: var(--text);
  }
  .sys-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
  @media (max-width: 900px) { .sys-grid { grid-template-columns: 1fr; } }
  .list { padding-top: 6px; padding-bottom: 6px; }
  .row { display: grid; grid-template-columns: 10px 18px 1fr auto auto; align-items: center; gap: 10px; padding: 9px 0; }
  .row + .row { border-top: 1px solid color-mix(in srgb, var(--border) 55%, transparent); }
  .pdot { width: 9px; height: 9px; border-radius: 50%; background: var(--faint); }
  .pdot.on { background: var(--ok); box-shadow: 0 0 7px color-mix(in srgb, var(--ok) 70%, transparent); }
  .pick { display: flex; align-items: center; justify-content: center; }
  .pick input { width: 14px; height: 14px; cursor: pointer; }
  .info { min-width: 0; display: flex; flex-direction: column; }
  .pname { font-weight: 550; font-size: 13px; color: var(--heading); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .pid { font-family: var(--mono); font-size: 11px; color: var(--faint); }
  .cmeta { font-family: var(--mono); font-size: 11px; color: var(--muted); text-align: right; }
  .sys-state { font-family: var(--mono); font-size: 11px; color: var(--faint); text-transform: uppercase; }
  .sys-state.up { color: var(--ok); }
  .grouplabel { font-family: var(--mono); font-size: 10.5px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--faint); font-weight: 600; margin: 12px 0 2px; }
  .ghost { background: transparent; border: 1px solid var(--border); color: var(--muted); padding: 4px 9px; font-size: 11.5px; border-radius: 7px; }
  .ghost:hover { color: var(--text); border-color: var(--border-strong); }
  .btn-accent.sm, .btn-danger.sm { padding: 4px 10px; font-size: 12px; border-radius: 7px; }
  .profile-hint { margin-top: 14px; font-size: 12px; color: var(--muted); line-height: 1.5; }

  .log-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.6); z-index: 60; display: flex; align-items: center; justify-content: center; padding: 24px; }
  .log-modal { background: var(--panel); border: 1px solid var(--border); border-radius: 12px; width: min(900px, 92vw); height: min(70vh, 620px); display: flex; flex-direction: column; overflow: hidden; box-shadow: var(--shadow); }
  .log-head { display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; background: var(--panel-2); border-bottom: 1px solid var(--border); }
  .log-title { font-size: 13px; color: var(--heading); font-weight: 600; }
  .log-id { color: var(--muted); font-weight: 400; font-size: 11px; }
  .log-head-r { display: flex; align-items: center; gap: 10px; }
  .log-live { font-size: 10px; color: var(--ok); text-transform: uppercase; letter-spacing: 0.05em; }
  .log-close { padding: 2px 9px; background: transparent; border: 0; }
  .log-body { flex: 1; margin: 0; padding: 12px 14px; overflow: auto; font-family: var(--mono); font-size: 12px; line-height: 1.45; color: #d6deeb; white-space: pre-wrap; word-break: break-word; background: #0b0e14; }
</style>
