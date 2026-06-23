<script>
  import { onMount, onDestroy } from 'svelte';
  import { api } from '../lib/api.js';
  import { config } from '../lib/config.js';

  let data = $state(null);
  let offline = $state(false);
  let failCount = 0;
  let timer;

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

  async function refresh() {
    try {
      data = await api.mirStatus();
      offline = false;
      failCount = 0;
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
    const base = config.poll.mirStatusMs;
    const delay = offline ? Math.min(base * Math.min(failCount, 8), 30000) : base;
    timer = setTimeout(refresh, delay);
  }

  onMount(refresh);
  onDestroy(() => clearTimeout(timer));
</script>

<div class="panel">
  <div class="panel-header">
    <h2>MiR200 · 192.168.1.13</h2>
    <div class="hdr-right">
      {#if data}
        <span class="badge {stateClass(data.state)}" class:stale={data.stale}>
          {data.state}{data.stale ? ` (${data.age_s}s)` : ''}
        </span>
      {:else if offline}
        <span class="badge">sin conexión</span>
      {/if}
      <button onclick={() => { failCount = 0; refresh(); }}>Actualizar</button>
    </div>
  </div>
  <div class="panel-body">
    {#if offline && !data}
      <div class="offline">
        MiR sin conexión — probablemente apagado.
        <div class="muted">Se reintenta automáticamente. Solo responde encendido y en Pause.</div>
      </div>
    {:else if data}
      <div class="battery">
        <div class="stat-label">Batería</div>
        <div class="bar"><div class="fill {batteryClass(data.battery_pct)}" style="width:{data.battery_pct}%"></div></div>
        <div class="stat-value">{data.battery_pct?.toFixed(1)}% · {fmtTime(data.battery_time_s)}</div>
      </div>
      <div class="stat-grid">
        <div><div class="stat-label">Posición</div><div class="stat-value mono">x {data.position?.x?.toFixed(2)} · y {data.position?.y?.toFixed(2)} · θ {deg(data.position?.orientation)}°</div></div>
        <div><div class="stat-label">Velocidad</div><div class="stat-value mono">{data.velocity?.linear?.toFixed(2)} m/s · {data.velocity?.angular?.toFixed(2)} rad/s</div></div>
        <div><div class="stat-label">Modo</div><div class="stat-value">{data.mode || '--'}</div></div>
        <div><div class="stat-label">Misión</div><div class="stat-value">{data.mission || '--'}</div></div>
        <div>
          <div class="stat-label">Errores</div>
          <div class="stat-value" class:has-err={data.errors?.length}>{data.errors?.length || 0}</div>
        </div>
      </div>
    {:else}
      <div class="muted">Cargando…</div>
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
  .offline { color: var(--text); }
  .muted { color: var(--muted); font-size: 12px; margin-top: 4px; }
</style>
