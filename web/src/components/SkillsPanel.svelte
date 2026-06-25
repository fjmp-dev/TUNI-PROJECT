<script>
  import { api } from '../lib/api.js';
  import { log } from '../lib/log.svelte.js';

  let arm = $state('left');
  let mass = $state(0.0);
  let cogX = $state(0.0);
  let cogY = $state(0.0);
  let cogZ = $state(0.0);
  let busy = $state(false);

  async function applyPayload() {
    busy = true;
    log(`Aplicando payload ${arm}: ${mass} kg…`, 'info');
    try {
      const r = await api.urPayload(arm, Number(mass), Number(cogX), Number(cogY), Number(cogZ));
      log(`Payload aplicado a ${r.arm}: ${r.mass} kg`, 'success');
    } catch (e) {
      log(`Payload falló: ${e.message}`, 'error');
    } finally {
      busy = false;
    }
  }
</script>

<div class="panel">
  <div class="panel-header"><h2>Smart Skills</h2></div>
  <div class="panel-body">
    <div class="skill">
      <div class="skill-title">Payload activo</div>
      <div class="row">
        <label>Brazo
          <select bind:value={arm}>
            <option value="left">Izquierdo</option>
            <option value="right">Derecho</option>
          </select>
        </label>
        <label>Masa (kg)
          <input type="number" min="0" max="5" step="0.1" bind:value={mass} />
        </label>
        <label>CoG x <input type="number" step="0.01" bind:value={cogX} /></label>
        <label>CoG y <input type="number" step="0.01" bind:value={cogY} /></label>
        <label>CoG z <input type="number" step="0.01" bind:value={cogZ} /></label>
        <button class="btn-accent" onclick={applyPayload} disabled={busy}>Aplicar</button>
      </div>
      <div class="note">No mueve el brazo; ajusta el modelo dinámico (masa y centro de gravedad de la herramienta).</div>
    </div>

    <div class="skill soon">
      <div class="skill-title">Freedrive · Force-mode · Align-to-plane <span class="badge">próximos</span></div>
      <div class="note">Siguientes skills: freedrive (guiar a mano) y force-mode / align-to-plane (con los sensores Nordbo F/T).</div>
    </div>
  </div>
</div>

<style>
  .skill { padding-bottom: 14px; }
  .skill + .skill { border-top: 1px solid var(--border); padding-top: 14px; }
  .skill-title { font-weight: 600; color: #fff; margin-bottom: 10px; display: flex; align-items: center; gap: 8px; }
  .row { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 12px; }
  label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--muted); }
  input, select { background: var(--panel-2); border: 1px solid var(--border); color: var(--text); padding: 5px 8px; border-radius: 6px; font: inherit; }
  input[type='number'] { width: 80px; }
  .note { font-size: 12px; color: var(--muted); margin-top: 8px; }
  .soon { opacity: 0.7; }
</style>
