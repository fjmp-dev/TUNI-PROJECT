<script>
  import { onMount, onDestroy } from 'svelte';
  import { api } from '../lib/api.js';
  import { config } from '../lib/config.js';

  let data = $state(null);
  let offline = $state(false);
  let failCount = 0;
  let timer;

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

  // Set on unmount. The poll is a setTimeout CHAIN, so clearTimeout() in onDestroy is not
  // enough: a request already in flight lands afterwards and re-arms the chain from its
  // `finally`, and the panel keeps polling the MiR forever — from every other tab, for the
  // life of the page. Found in the 2026-07-14 audit: /api/mir/status was being requested
  // from the Terminal tab.
  let dead = false;

  async function refresh() {
    if (dead) return;
    try {
      const r = await api.mirStatus();
      // 200 {available:false} = the MiR is simply powered off (not a server fault).
      if (r && r.available === false) {
        data = null;
        offline = true;
        failCount++;
      } else {
        data = r;
        offline = false;
        failCount = 0;
      }
    } catch {
      offline = true;
      failCount++;
    } finally {
      schedule();
    }
  }

  // Back off when the MiR is unreachable (usually powered off) so we don't hammer
  // the backend or flood the console every few seconds. Reset on success.
  function schedule() {
    clearTimeout(timer);
    if (dead) return;
    const base = config.poll.mirStatusMs;
    const delay = offline ? Math.min(base * Math.min(failCount, 8), 30000) : base;
    timer = setTimeout(refresh, delay);
  }

  onMount(refresh);
  onDestroy(() => {
    dead = true;
    clearTimeout(timer);
  });
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
      <button onclick={() => { failCount = 0; refresh(); }}>Refresh</button>
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
