// Shared event log, reactive via Svelte 5 runes. Imported by any component that
// needs to record or render events.
export const logState = $state({ entries: [] });

export function log(message, kind = 'info') {
  const time = new Date().toLocaleTimeString();
  logState.entries.push({ time, message, kind });
  // Keep the log bounded.
  if (logState.entries.length > 200) logState.entries.shift();
}

export function clearLog() {
  logState.entries = [];
}
