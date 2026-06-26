<script>
  import { login } from '../lib/auth.svelte.js';

  let username = $state('');
  let password = $state('');
  let error = $state('');
  let busy = $state(false);

  async function submit(e) {
    e.preventDefault();
    busy = true;
    error = '';
    try {
      await login(username, password);
    } catch {
      error = 'Invalid credentials';
    } finally {
      busy = false;
    }
  }
</script>

<div class="screen">
  <form class="box" onsubmit={submit}>
    <h1>MIR Suite</h1>
    <p class="sub">Sign in to continue</p>
    <label>User
      <input type="text" bind:value={username} autocomplete="username" autofocus />
    </label>
    <label>Password
      <input type="password" bind:value={password} autocomplete="current-password" />
    </label>
    {#if error}<div class="err">{error}</div>{/if}
    <button class="btn-accent" type="submit" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
  </form>
</div>

<style>
  .screen { min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; }
  .box {
    width: 100%; max-width: 320px; background: var(--panel); border: 1px solid var(--border);
    border-radius: 12px; padding: 28px 26px; display: flex; flex-direction: column; gap: 14px;
  }
  h1 { font-size: 22px; color: #fff; }
  .sub { margin: -8px 0 6px; color: var(--muted); font-size: 13px; }
  label { display: flex; flex-direction: column; gap: 5px; font-size: 12px; color: var(--muted); }
  input {
    background: var(--panel-2); border: 1px solid var(--border); color: var(--text);
    padding: 9px 11px; border-radius: 7px; font: inherit;
  }
  .err { color: var(--err); font-size: 13px; }
  button { margin-top: 6px; padding: 10px; }
</style>
