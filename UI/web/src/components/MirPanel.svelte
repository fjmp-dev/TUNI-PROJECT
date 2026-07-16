<script>
  import { onMount, onDestroy } from 'svelte';
  import { api } from '../lib/api.js';
  import { mirState, startMir, stopMir, refreshMir } from '../lib/mir.svelte.js';

  // Read-through to the shared, ref-counted MiR poller (also used by the Overview tile),
  // so there is a single /api/mir/status poll no matter how many views are mounted.
  const data = $derived(mirState.data);
  const offline = $derived(mirState.offline);

  // The address comes from the backend (config/.env). This header used to hardcode
  // 192.168.1.13 -- an IP the MiR has not had for a long time -- so the panel named
  // the wrong robot while polling the right one.
  let mirIp = $state('');
  api.suiteConfig().then((c) => (mirIp = c.mir_ip)).catch(() => {});

  const stateClass = (s) => {
    const x = (s || '').toLowerCase();
    if (x.includes('error')) return 'err';
    if (x.includes('run')) return 'ok';
    if (x.includes('pause')) return 'warn';
    return '';
  };
  const batteryClass = (p) => (p > 40 ? 'ok' : p >= 20 ? 'warn' : 'err');
  const fmtTime = (s) => (s ? `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m` : '--');
  const deg = (rad) => ((rad ?? 0) * 180 / Math.PI).toFixed(1);

  // The shared store handles the poll + offline backoff + the in-flight-re-arm guard
  // (via its ref count); this component just holds a ref while mounted.
  onMount(startMir);
  onDestroy(stopMir);
</script>

<div class="panel">
  <div class="panel-header">
    <h2>MiR200{mirIp ? ` · ${mirIp}` : ''}</h2>
    <div class="hdr-right">
      {#if data}
        <span class="badge {stateClass(data.state)}" class:stale={data.stale}>
          {data.state}{data.stale ? ` (${data.age_s}s)` : ''}
        </span>
      {:else if offline}
        <span class="badge">offline</span>
      {/if}
      <button onclick={refreshMir}>Refresh</button>
    </div>
  </div>
  <div class="panel-body">
    {#if offline && !data}
      <div class="offline">
        MiR offline — likely powered off.
        <div class="muted">Retrying automatically. It only responds when powered on and in Pause.</div>
      </div>
    {:else if data}
      {#if data.stale}
        <div class="stale-banner">Data from {data.age_s}s ago — MiR didn't respond (intermittent). Retrying…</div>
      {/if}
      <div class="battery">
        <div class="stat-label">Battery</div>
        <div class="bar"><div class="fill {batteryClass(data.battery_pct)}" style="width:{data.battery_pct}%"></div></div>
        <div class="stat-value">{data.battery_pct?.toFixed(1)}% · {fmtTime(data.battery_time_s)}</div>
      </div>
      <div class="stat-grid">
        <div><div class="stat-label">Position</div><div class="stat-value mono">x {data.position?.x?.toFixed(2)} · y {data.position?.y?.toFixed(2)} · θ {deg(data.position?.orientation)}°</div></div>
        <div><div class="stat-label">Velocity</div><div class="stat-value mono">{data.velocity?.linear?.toFixed(2)} m/s · {data.velocity?.angular?.toFixed(2)} rad/s</div></div>
        <div><div class="stat-label">Mode</div><div class="stat-value">{data.mode || '--'}</div></div>
        <div><div class="stat-label">Mission</div><div class="stat-value">{data.mission || '--'}</div></div>
        <div>
          <div class="stat-label">Errors</div>
          <div class="stat-value" class:has-err={data.errors?.length}>{data.errors?.length || 0}</div>
        </div>
      </div>
    {:else}
      <div class="muted">Loading…</div>
    {/if}
  </div>
</div>

<style>
  .hdr-right { display: flex; align-items: center; gap: 10px; }
  .battery { margin-bottom: 14px; }
  .bar { height: 10px; background: var(--panel-2); border-radius: 6px; overflow: hidden; margin: 5px 0; }
  .fill { height: 100%; transition: width 0.4s; }
  .fill.ok { background: var(--ok); }
  .fill.warn { background: var(--warn); }
  .fill.err { background: var(--err); }
  .has-err { color: var(--err); }
  .stale-banner {
    background: rgba(224, 138, 30, 0.12);
    border: 1px solid var(--warn);
    color: var(--warn);
    font-size: 12px;
    padding: 6px 10px;
    border-radius: 6px;
    margin-bottom: 12px;
  }
  .offline { color: var(--text); }
  .muted { color: var(--muted); font-size: 12px; margin-top: 4px; }
</style>
