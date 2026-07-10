// Theme (light/dark) toggle. Persisted in localStorage; when unset the page
// follows the OS preference (prefers-color-scheme) via CSS. Setting a value
// stamps data-theme on <html>, which overrides the media query in both directions.
const KEY = 'mir_theme';

function stored() {
  try { return localStorage.getItem(KEY); } catch { return null; }
}

export const themeState = $state({ mode: stored() || 'system' });

function apply(mode) {
  const root = document.documentElement;
  if (mode === 'light' || mode === 'dark') root.setAttribute('data-theme', mode);
  else root.removeAttribute('data-theme');
}

export function initTheme() {
  apply(themeState.mode);
}

// Resolve what's actually showing right now (for the toggle icon).
export function effectiveTheme() {
  if (themeState.mode === 'light' || themeState.mode === 'dark') return themeState.mode;
  return matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

// Simple flip between light and dark (drops "system" once the user chooses).
export function toggleTheme() {
  const next = effectiveTheme() === 'dark' ? 'light' : 'dark';
  themeState.mode = next;
  try { localStorage.setItem(KEY, next); } catch {}
  apply(next);
}
