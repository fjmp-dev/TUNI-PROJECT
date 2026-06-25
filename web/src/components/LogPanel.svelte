<script>
  import { logState, clearLog } from '../lib/log.svelte.js';
</script>

<div class="panel">
  <div class="panel-header">
    <h2>Log</h2>
    <button onclick={clearLog}>Clear</button>
  </div>
  <div class="panel-body log">
    {#each logState.entries.slice().reverse() as e}
      <div class="log-entry {e.kind}"><span class="t">{e.time}</span> {e.message}</div>
    {/each}
    {#if logState.entries.length === 0}
      <div class="empty">No events.</div>
    {/if}
  </div>
</div>

<style>
  .log { max-height: 180px; overflow-y: auto; font-family: var(--mono); font-size: 12px; }
  .log-entry { padding: 2px 0; }
  .log-entry .t { color: var(--muted); margin-right: 6px; }
  .log-entry.success { color: var(--ok); }
  .log-entry.error { color: var(--err); }
  .empty { color: var(--muted); }
</style>
