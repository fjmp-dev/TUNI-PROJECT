<script>
  import { onMount, onDestroy } from 'svelte';
  import { api } from '../lib/api.js';
  import { log } from '../lib/log.svelte.js';

  // Nordbo NRS wrist force/torque sensors. The backend reads each sensor's native
  // WebSocket and serves the latest [Fx,Fy,Fz,Tx,Ty,Tz]; we poll it here.
  let sensors = $state({ left: null, right: null });
  let timer;
  const F_MAX = 50; // N   full-scale for the bar
  const T_MAX = 5;  // Nm  full-scale for the bar

  async function tick() {
    try {
      const r = await api.force();
      if (r?.sensors) sensors = r.sensors;
    } catch { /* keep last */ }
  }
  async function tare(side) {
    try { await api.forceTare(side); log(`Tared ${side} force sensor`, 'success'); }
    catch (e) { log(`Tare failed: ${e.message}`, 'error'); }
  }
  // Pause/resume the backend's reader so the sensor's native web UI can grab the
  // single WebSocket slot the sensor exposes on :2003. The native UI runs at
  // http://<sensor-ip> (port 80) and tries to open its own WS to :2003.
  const NATIVE_URL = { left: 'http://192.168.1.112', right: 'http://192.168.1.113' };
  async function disconnect(side) {
    try {
      const r = await api.forceDisconnect(side);
      log(`${side} reader paused — open ${r.ip} for the native Nordbo UI`, 'info');
    } catch (e) { log(`Pause failed: ${e.message}`, 'error'); }
  }
  async function connect(side) {
    try {
      await api.forceConnect(side);
      log(`${side} reader resumed`, 'success');
    } catch (e) { log(`Resume failed: ${e.message}`, 'error'); }
  }

  onMount(() => { tick(); timer = setInterval(tick, 150); });
  onDestroy(() => clearInterval(timer));

  const AXES_F = [['fx', 'Fx'], ['fy', 'Fy'], ['fz', 'Fz']];
  const AXES_T = [['tx', 'Tx'], ['ty', 'Ty'], ['tz', 'Tz']];
  // half-width % of the bar (0..50), from a signed value scaled to max
  const half = (v, max) => Math.min(50, (Math.abs(v) / max) * 50);
</script>

<div class="panel">
  <div class="panel-header">
    <h2>Force / Torque — Nordbo</h2>
    <span class="badge">wrist sensors</span>
  </div>
  <div class="panel-body">
    <div class="wrists">
      {#each ['left', 'right'] as side}
        {@const s = sensors[side]}
        <div class="wrist">
          <div class="wrist-head">
            <span class="dot" class:on={s?.connected && !s?.paused}></span>
            <span class="wname">{side === 'left' ? 'Left' : 'Right'} wrist</span>
            <button class="tare" onclick={() => tare(side)} disabled={!s?.connected || s?.paused} title="Zero the sensor">Tare</button>
            {#if s?.paused}
              <button class="resume" onclick={() => connect(side)} title="Resume reading this sensor in mirui">Resume</button>
            {:else}
              <button class="pause" onclick={() => disconnect(side)} title="Free the WebSocket slot so the sensor's native UI can connect">Use native UI</button>
            {/if}
          </div>

          {#if s?.paused}
            <div class="banner">
              Reader paused. The native Nordbo UI can now connect to
              <a href={NATIVE_URL[side]} target="_blank" rel="noreferrer">{NATIVE_URL[side]}</a>.
            </div>
          {:else if s}
            <div class="grp">Force <span class="unit">N</span></div>
            {#each AXES_F as [k, lbl]}
              <div class="axis">
                <span class="lbl">{lbl}</span>
                <div class="bar">
                  <span class="zero"></span>
                  <div class="fill" class:neg={s[k] < 0}
                       style="width:{half(s[k], F_MAX)}%; {s[k] < 0 ? 'right' : 'left'}:50%"></div>
                </div>
                <span class="val">{s[k].toFixed(2)}</span>
              </div>
            {/each}

            <div class="grp">Torque <span class="unit">Nm</span></div>
            {#each AXES_T as [k, lbl]}
              <div class="axis">
                <span class="lbl">{lbl}</span>
                <div class="bar">
                  <span class="zero"></span>
                  <div class="fill" class:neg={s[k] < 0}
                       style="width:{half(s[k], T_MAX)}%; {s[k] < 0 ? 'right' : 'left'}:50%"></div>
                </div>
                <span class="val">{s[k].toFixed(3)}</span>
              </div>
            {/each}
          {:else}
            <div class="muted">no data</div>
          {/if}
        </div>
      {/each}
    </div>
    <div class="note">
      Live wrist force/torque from the Nordbo NRS sensors (read directly over their WebSocket).
      Bars are centered at zero (± full-scale {F_MAX} N / {T_MAX} Nm). <b>Tare</b> zeroes a sensor.
      <b>Use native UI</b> releases the single WebSocket slot so the sensor's own dashboard can connect.
    </div>
  </div>
</div>

<style>
  .wrists { display: flex; gap: 24px; flex-wrap: wrap; }
  .wrist { flex: 1; min-width: 260px; }
  .wrist-head { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
  .dot { width: 9px; height: 9px; border-radius: 50%; background: var(--err); flex: none; }
  .dot.on { background: var(--ok); box-shadow: 0 0 6px var(--ok); }
  .wname { font-weight: 600; color: var(--heading); flex: 1; }
  .tare, .pause, .resume { font-size: 11px; padding: 3px 10px; }
  .tare:disabled { opacity: 0.4; cursor: not-allowed; }
  .pause { background: var(--warn); color: #000; border: 1px solid var(--warn); border-radius: 4px; cursor: pointer; }
  .pause:hover { filter: brightness(1.1); }
  .resume { background: var(--ok); color: #000; border: 1px solid var(--ok); border-radius: 4px; cursor: pointer; font-weight: 600; }
  .resume:hover { filter: brightness(1.1); }
  .banner {
    margin: 6px 0 10px; padding: 8px 10px; border-radius: 6px;
    background: rgba(237, 177, 32, 0.12); border: 1px solid var(--warn);
    color: var(--warn); font-size: 12px; line-height: 1.4;
  }
  .banner a { color: var(--warn); text-decoration: underline; margin-left: 4px; }
  .grp { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; margin: 10px 0 4px; }
  .grp .unit { text-transform: none; opacity: 0.7; }
  .axis { display: flex; align-items: center; gap: 8px; margin: 3px 0; }
  .lbl { width: 22px; font-size: 12px; color: var(--muted); }
  .bar {
    flex: 1; height: 12px; position: relative; border-radius: 6px;
    background: var(--panel-3); border: 1px solid var(--border); overflow: hidden;
  }
  .zero { position: absolute; left: 50%; top: 0; bottom: 0; width: 1px; background: var(--border-strong); }
  .fill { position: absolute; top: 0; bottom: 0; background: var(--accent); }
  .fill.neg { background: var(--warn); }
  .val { width: 62px; text-align: right; font-family: var(--mono); font-size: 12px; }
  .muted { color: var(--muted); font-size: 12px; }
  .note { margin-top: 14px; font-size: 11px; color: var(--muted); line-height: 1.5; }
</style>
