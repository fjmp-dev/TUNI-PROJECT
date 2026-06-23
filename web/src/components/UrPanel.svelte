<script>
  import { onMount, onDestroy } from 'svelte';
  import { api } from '../lib/api.js';
  import { config } from '../lib/config.js';
  import { log } from '../lib/log.svelte.js';

  let status = $state({ container_running: false, driver_running: false });
  let joints = $state(null);
  let busy = $state(false);
  let statusTimer, jointsTimer;

  const JOINTS = [
    ['shoulder_pan_joint', 'shoulder_pan'],
    ['shoulder_lift_joint', 'shoulder_lift'],
    ['elbow_joint', 'elbow'],
    ['wrist_1_joint', 'wrist_1'],
    ['wrist_2_joint', 'wrist_2'],
    ['wrist_3_joint', 'wrist_3'],
  ];

  const fmt = (v) => (v == null ? '--' : v.toFixed(3));

  async function refreshStatus() {
    try {
      status = await api.urStatus();
    } catch {
      status = { container_running: false, driver_running: false };
    }
  }

  async function refreshJoints() {
    try {
      joints = await api.urJoints();
    } catch {
      joints = null;
    }
  }

  async function start() {
    busy = true;
    log('Iniciando driver UR...', 'info');
    try {
      await api.urStart();
      log('Driver UR lanzándose (puede tardar ~60-90s)', 'success');
    } catch (e) {
      log(`Start falló: ${e.message}`, 'error');
    } finally {
      busy = false;
    }
  }

  async function stop() {
    busy = true;
    log('Deteniendo driver UR...', 'info');
    try {
      await api.urStop();
      log('Driver UR detenido', 'success');
    } catch (e) {
      log(`Stop falló: ${e.message}`, 'error');
    } finally {
      busy = false;
    }
  }

  async function move(arm, delta) {
    log(`Moviendo ${arm} elbow ${delta > 0 ? '+' : ''}${delta}...`, 'info');
    try {
      const r = await api.urMove(arm, 'elbow', delta);
      log(r.message || `OK ${arm} elbow ${delta}`, 'success');
    } catch (e) {
      log(`Move falló: ${e.message}`, 'error');
    }
  }

  onMount(() => {
    refreshStatus();
    refreshJoints();
    statusTimer = setInterval(refreshStatus, config.poll.urStatusMs);
    jointsTimer = setInterval(refreshJoints, config.poll.urJointsMs);
  });
  onDestroy(() => {
    clearInterval(statusTimer);
    clearInterval(jointsTimer);
  });
</script>

<div class="panel">
  <div class="panel-header">
    <h2>Brazos UR5e · .102 / .103</h2>
    <div class="hdr-right">
      <span class="badge {status.driver_running ? 'ok' : ''}">
        {status.driver_running ? 'driver activo' : status.container_running ? 'driver parado' : 'sin contenedor'}
      </span>
      <button class="btn-accent" onclick={start} disabled={busy || status.driver_running}>Start</button>
      <button class="btn-danger" onclick={stop} disabled={busy || !status.driver_running}>Stop</button>
    </div>
  </div>
  <div class="panel-body">
    <div class="joints-meta">
      {#if joints && !joints.stale}
        12 joints @ 400Hz <span class="muted">(age {joints.age_s?.toFixed?.(3) ?? '?'}s)</span>
      {:else if joints && joints.stale}
        <span class="muted">joints sin datos frescos</span>
      {:else}
        <span class="muted">sin joints (driver parado)</span>
      {/if}
    </div>

    <div class="arms">
      {#each ['left', 'right'] as arm}
        <div class="arm">
          <div class="arm-title">{arm === 'left' ? 'Izquierdo' : 'Derecho'}</div>
          <div class="joint-grid">
            {#each JOINTS as [key, label]}
              <div class="jname">{label}</div>
              <div class="jval mono">{fmt(joints?.[arm]?.[key])}</div>
            {/each}
          </div>
          <div class="elbow-controls">
            <span class="muted">codo:</span>
            <button onclick={() => move(arm, -0.1)} disabled={!status.driver_running}>-0.1</button>
            <button onclick={() => move(arm, -0.01)} disabled={!status.driver_running}>-0.01</button>
            <button onclick={() => move(arm, 0.01)} disabled={!status.driver_running}>+0.01</button>
            <button onclick={() => move(arm, 0.1)} disabled={!status.driver_running}>+0.1</button>
          </div>
        </div>
      {/each}
    </div>

    <div class="safety">
      Nota: los brazos están montados viendo hacia la espalda del MiR. Las direcciones +/− pueden
      ser contrarias a lo esperado. Solo se mueve el codo; verificar visualmente.
    </div>
  </div>
</div>

<style>
  .hdr-right { display: flex; align-items: center; gap: 8px; }
  .joints-meta { font-size: 12px; color: var(--text); margin-bottom: 12px; }
  .muted { color: var(--muted); }
  .arms { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  .arm-title { font-weight: 600; margin-bottom: 8px; color: #fff; }
  .joint-grid { display: grid; grid-template-columns: auto 1fr; gap: 3px 10px; align-items: baseline; }
  .jname { color: var(--muted); font-size: 12px; }
  .jval { text-align: right; }
  .elbow-controls { display: flex; align-items: center; gap: 6px; margin-top: 10px; flex-wrap: wrap; }
  .elbow-controls button { padding: 4px 9px; }
  .safety { margin-top: 14px; font-size: 12px; color: var(--warn); border-top: 1px solid var(--border); padding-top: 10px; }
</style>
