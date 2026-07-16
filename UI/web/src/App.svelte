<script>
  import { onMount } from 'svelte';
  import { connectRos } from './lib/ros.svelte.js';
  import { auth } from './lib/auth.svelte.js';
  import { api } from './lib/api.js';
  import { profile, setProfile } from './lib/profiles.svelte.js';
  import { initTheme } from './lib/theme.svelte.js';
  import Login from './components/Login.svelte';
  import TopBar from './components/TopBar.svelte';
  import Overview from './components/Overview.svelte';
  import UrPanel from './components/UrPanel.svelte';
  import MirPanel from './components/MirPanel.svelte';
  import CameraPanel from './components/CameraPanel.svelte';
  import ForcePanel from './components/ForcePanel.svelte';
  import SkillsPanel from './components/SkillsPanel.svelte';
  import SystemView from './components/SystemView.svelte';
  import TerminalPanel from './components/TerminalPanel.svelte';
  import LogPanel from './components/LogPanel.svelte';

  // The view lives in the URL hash (#/arms, #/system, ...), not in component state:
  // a reload keeps you on the tab you were on, back/forward moves between tabs, and
  // a tab can be linked/bookmarked. nav() only writes the hash; the hashchange
  // listener is the single place that switches the view, so both entry paths
  // (clicking a tab, editing the URL) behave identically.
  const VIEWS = ['overview', 'arms', 'mir', 'camera', 'system', 'terminal'];
  const viewFromHash = () => {
    const v = window.location.hash.replace(/^#\/?/, '');
    return VIEWS.includes(v) ? v : 'overview';
  };
  let view = $state(viewFromHash());
  function nav(v) {
    // Guard: only admins can reach the terminal (backend enforces it too).
    if (v === 'terminal' && profile.role !== 'admin') return;
    if ('#/' + v === window.location.hash) return; // same tab: no-op (no scroll jump)
    window.location.hash = '/' + v;
  }
  function syncView() {
    const v = viewFromHash();
    // Deep link to #/terminal by a non-admin: bounce to overview once the profile
    // is known (the backend refuses the terminal socket for non-admins anyway).
    if (v === 'terminal' && profile.username && profile.role !== 'admin') {
      window.location.hash = '/overview';
      return;
    }
    view = v;
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  // Connect rosbridge once, after login. On reload the token is present but the
  // profile store is empty, so hydrate it from /api/me.
  let started = false;
  $effect(() => {
    if (auth.token && !started) {
      started = true;
      connectRos();
      if (!profile.username) api.me().then(setProfile).catch(() => {});
    }
  });

  // Bounce a non-admin off #/terminal. syncView() only covers hashchange, so a direct
  // load of #/terminal (or the profile hydrating after load) would otherwise leave a
  // non-admin staring at a blank view. This reactive guard fires on first render and
  // whenever the role becomes known.
  $effect(() => {
    if (view === 'terminal' && profile.username && profile.role !== 'admin') {
      window.location.hash = '/overview';
    }
  });

  onMount(() => {
    initTheme();
    window.addEventListener('hashchange', syncView);
    return () => window.removeEventListener('hashchange', syncView);
  });
</script>

{#if !auth.token}
  <Login />
{:else}
  <TopBar {view} onNav={nav} />
  <main class="content">
    {#if view === 'overview'}
      <section class="view"><Overview onNav={nav} /></section>
    {:else if view === 'arms'}
      <section class="view">
        <div class="view-head">
          <div><div class="eyebrow">UR5e · dual</div><h1>Arms</h1>
          <p>Live joint telemetry, jog controls, payload and hand-guiding (freedrive).</p></div>
        </div>
        <div class="stack">
          <UrPanel />
          <SkillsPanel />
          <ForcePanel />
        </div>
      </section>
    {:else if view === 'mir'}
      <section class="view">
        <div class="view-head"><div><div class="eyebrow">Mobile base</div><h1>MiR 200</h1>
          <p>Battery, pose, mission and velocity. Responds only when powered on and in Pause.</p></div></div>
        <MirPanel />
      </section>
    {:else if view === 'camera'}
      <section class="view">
        <div class="view-head"><div><div class="eyebrow">Orbbec Gemini 335Lg</div><h1>Camera</h1>
          <p>Live color stream over rosbridge. Depth and color share one USB device — only one runs at a time.</p></div></div>
        <CameraPanel />
      </section>
    {:else if view === 'system'}
      <section class="view"><SystemView /></section>
    {:else if view === 'terminal' && profile.role === 'admin'}
      <section class="view">
        <div class="view-head"><div><div class="eyebrow">admin only</div><h1>Terminal</h1>
          <p>Shell into a running container over an authenticated WebSocket.</p></div></div>
        <TerminalPanel />
      </section>
    {/if}

    <div class="activity"><LogPanel /></div>
  </main>
{/if}

<style>
  .content { max-width: 1320px; margin: 0 auto; padding: 22px 18px 56px; }
  .view { animation: fade 0.2s ease; }
  @keyframes fade { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }
  @media (prefers-reduced-motion: reduce) { .view { animation: none; } }
  .stack { display: flex; flex-direction: column; gap: 14px; }
  .activity { margin-top: 16px; }

  /* Shared view header styling (used by inline views + Overview/System components). */
  :global(.view-head) { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; margin-bottom: 18px; flex-wrap: wrap; }
  :global(.view-head h1) { font-size: 21px; }
  :global(.view-head p) { margin: 3px 0 0; color: var(--muted); font-size: 13.5px; max-width: 62ch; }
  :global(.eyebrow) { font-family: var(--mono); font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase; color: var(--accent); font-weight: 600; }
  :global(.btn.accent) { background: var(--accent); border-color: var(--accent); color: #fff; }
  :global(.btn.accent:hover:not(:disabled)) { background: color-mix(in srgb, var(--accent) 85%, #000); }
</style>
