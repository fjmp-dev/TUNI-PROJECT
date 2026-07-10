<script>
  import { api } from '../lib/api.js';
  import { log } from '../lib/log.svelte.js';
  import { freedrive } from '../lib/skills.svelte.js';

  let arm = $state('left');
  let mass = $state(0.0);
  let cogX = $state(0.0);
  let cogY = $state(0.0);
  let cogZ = $state(0.0);
  let busy = $state(false);
  let fdBusy = $state(false);
  // Tracks the payload actually applied to each arm this session.
  let appliedPayload = $state({ left: 0, right: 0 });
  const FREEDRIVE_MIN_PAYLOAD = 1; // kg — required before going compliant

  // Collapsible panel (state remembered in localStorage).
  function loadCollapsed() {
    try { return localStorage.getItem('mir_skills_collapsed') === '1'; } catch { return false; }
  }
  let collapsed = $state(loadCollapsed());
  function toggleCollapsed() {
    collapsed = !collapsed;
    try { localStorage.setItem('mir_skills_collapsed', collapsed ? '1' : '0'); } catch {}
  }

  async function toggleFreedrive(side) {
    const target = !freedrive[side];
    // Require an active payload > 1 kg before enabling, so the arm can hold its
    // own weight / tool when it goes compliant.
    if (target && appliedPayload[side] <= FREEDRIVE_MIN_PAYLOAD) {
      log(
        `Freedrive ${side} blocked: set an active payload greater than ${FREEDRIVE_MIN_PAYLOAD} kg for the ${side} arm first (Active payload above).`,
        'error'
      );
      return;
    }
    fdBusy = true;
    log(`Freedrive ${side}: ${target ? 'enabling' : 'disabling'}…`, 'info');
    try {
      const r = await api.urFreedrive(side, target);
      freedrive[side] = r.freedrive;
      log(`Freedrive ${side} ${r.freedrive ? 'ON — you can hand-guide now' : 'OFF'}`, 'success');
    } catch (e) {
      log(`Freedrive ${side} failed: ${e.message}`, 'error');
    } finally {
      fdBusy = false;
    }
  }

  async function applyPayload() {
    busy = true;
    log(`Applying payload ${arm}: ${mass} kg…`, 'info');
    try {
      const r = await api.urPayload(arm, Number(mass), Number(cogX), Number(cogY), Number(cogZ));
      appliedPayload[r.arm] = r.mass;
      log(`Payload applied to ${r.arm}: ${r.mass} kg`, 'success');
    } catch (e) {
      log(`Payload failed: ${e.message}`, 'error');
    } finally {
      busy = false;
    }
  }
</script>

<div class="panel">
  <div class="panel-header hdr-toggle" onclick={toggleCollapsed} role="button" tabindex="0">
    <div class="hdr-title">
      <h2>Smart Skills</h2>
      <span class="hdr-desc">Set the arm payload and hand-guide (freedrive) the UR5e arms — no coding needed.</span>
    </div>
    <span class="chev">{collapsed ? '▸' : '▾'}</span>
  </div>
  {#if !collapsed}
  <div class="panel-body">
    <div class="skill">
      <div class="skill-title">Active payload</div>
      <div class="row">
        <label>Arm
          <select bind:value={arm}>
            <option value="left">Left</option>
            <option value="right">Right</option>
          </select>
        </label>
        <label>Mass (kg)
          <input type="number" min="0" max="5" step="0.1" bind:value={mass} />
        </label>
        <label>CoG x (m) <input type="number" step="0.01" bind:value={cogX} /></label>
        <label>CoG y (m) <input type="number" step="0.01" bind:value={cogY} /></label>
        <label>CoG z (m) <input type="number" step="0.01" bind:value={cogZ} /></label>
        <button class="btn-accent" onclick={applyPayload} disabled={busy}>Apply</button>
      </div>
      <div class="note">
        Tells the arm the mass and <strong>center of gravity (CoG)</strong> of the mounted tool, so its
        dynamics/collision detection are correct. CoG x/y/z is the offset (in metres) of the tool's
        mass from the wrist flange. This does not move the arm.
      </div>
    </div>

    <div class="skill">
      <div class="skill-title">Freedrive (hand-guide)</div>
      <div class="note req">
        <strong>Requires an active payload &gt; 1 kg</strong> on that arm before it can be enabled — set
        and Apply it in <em>Active payload</em> above so the arm holds its own weight when it goes compliant.
        {#each ['left', 'right'] as side}
          <span class="pl-state" class:ok={appliedPayload[side] > 1}>
            {side}: {appliedPayload[side] > 1 ? `${appliedPayload[side]} kg ✓` : 'no payload set'}
          </span>
        {/each}
      </div>
      <div class="row">
        {#each ['left', 'right'] as side}
          <button class="fd-btn" class:on={freedrive[side]} disabled={fdBusy || appliedPayload[side] <= 1} onclick={() => toggleFreedrive(side)}>
            {side === 'left' ? 'Left' : 'Right'}: {freedrive[side] ? 'ON — click to disable' : 'enable'}
          </button>
        {/each}
      </div>
      <div class="note danger">
        Makes the arm <strong>compliant</strong> (movable by hand) — hold it before enabling and keep clear of pinch
        points. It auto-disengages if the connection drops. While ON, that arm's elbow buttons are disabled.
      </div>
    </div>

    <div class="skill soon">
      <div class="skill-title">Force-mode · Align-to-plane <span class="badge">soon</span></div>
      <div class="note">Needs the Nordbo F/T sensors integrated first.</div>
    </div>
  </div>
  {/if}
</div>

<style>
  .hdr-toggle { cursor: pointer; user-select: none; }
  .hdr-title { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
  .hdr-desc { font-size: 11px; color: var(--muted); font-weight: 400; line-height: 1.3; }
  .chev { color: var(--muted); font-size: 12px; flex: none; margin-left: 10px; }

  .skill { padding-bottom: 14px; }
  .skill + .skill { border-top: 1px solid var(--border); padding-top: 14px; }
  .skill-title { font-weight: 600; color: var(--heading); margin-bottom: 10px; display: flex; align-items: center; gap: 8px; }
  .row { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 12px; }
  label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--muted); }
  input, select { background: var(--panel-2); border: 1px solid var(--border); color: var(--text); padding: 5px 8px; border-radius: 6px; font: inherit; }
  input[type='number'] { width: 84px; }
  .note { font-size: 12px; color: var(--muted); margin-top: 8px; line-height: 1.5; max-width: 720px; }
  .note.danger { color: var(--err); }
  .note.req { color: #e0a44e; }
  .pl-state { display: inline-block; margin-left: 10px; padding: 1px 8px; border-radius: 10px; background: var(--panel-2); border: 1px solid var(--border); font-size: 11px; color: var(--err); }
  .pl-state.ok { color: #2e9e4f; }
  .soon { opacity: 0.7; }
  .fd-btn { min-width: 150px; }
  .fd-btn.on {
    background: var(--err);
    border-color: var(--err);
    color: #fff;
  }
</style>
