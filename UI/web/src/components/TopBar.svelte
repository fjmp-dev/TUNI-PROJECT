<script>
  import { rosState } from '../lib/ros.svelte.js';
  import { logout } from '../lib/auth.svelte.js';
  import { profile, canControl } from '../lib/profiles.svelte.js';
  import { nodesState } from '../lib/nodes.svelte.js';
  import { themeState, effectiveTheme, toggleTheme } from '../lib/theme.svelte.js';
  import { api } from '../lib/api.js';
  import { log } from '../lib/log.svelte.js';

  let { view = 'overview', onNav } = $props();

  // Tabs. Terminal is admin-only (backend enforces it too).
  const TABS = [
    { id: 'overview', label: 'Overview' },
    { id: 'arms', label: 'Arms' },
    { id: 'mir', label: 'MiR' },
    { id: 'camera', label: 'Camera' },
    { id: 'system', label: 'System' },
    { id: 'terminal', label: 'Terminal', admin: true },
  ];
  const tabs = $derived(TABS.filter((t) => !t.admin || profile.role === 'admin'));

  // Live "running / total" of individual nodes for the System tab badge.
  const nodeCount = $derived.by(() => {
    const n = nodesState.nodes || [];
    return { up: n.filter((x) => x.running).length, total: n.length };
  });

  const initial = $derived((profile.username || '?').charAt(0).toUpperCase());
  // Re-evaluates when the user toggles (themeState.mode is reactive).
  const dark = $derived((themeState.mode, effectiveTheme() === 'dark'));

  // ---- user management (admin) ----
  let showCreate = $state(false);
  let showManage = $state(false);
  let showMenu = $state(false);
  let nu = $state({ username: '', password: '', role: 'user', can_control: false });
  let creating = $state(false);
  let users = $state([]);
  let editingUser = $state(null);
  let editData = $state({ role: '', password: '', can_control: false });

  async function createUser() {
    if (!nu.username.trim() || !nu.password) return;
    creating = true;
    try {
      await api.createUser(nu.username.trim(), nu.password, nu.role, nu.can_control);
      log(`User '${nu.username.trim()}' created (${nu.role})`, 'success');
      showCreate = false;
      nu = { username: '', password: '', role: 'user', can_control: false };
    } catch (e) {
      log(`Create user failed: ${e.message}`, 'error');
    } finally {
      creating = false;
    }
  }

  async function loadUsers() {
    try { users = (await api.listUsers())?.users || []; }
    catch (e) { log(`Failed to load users: ${e.message}`, 'error'); }
  }
  function openManage() { showManage = true; showMenu = false; loadUsers(); }
  function startEdit(u) { editingUser = u.username; editData = { role: u.role, password: '', can_control: !!u.can_control }; }
  async function saveEdit() {
    if (!editingUser) return;
    try {
      const updates = { role: editData.role, can_control: editData.can_control };
      if (editData.password) updates.password = editData.password;
      await api.updateUser(editingUser, updates);
      log(`User '${editingUser}' updated`, 'success');
      editingUser = null; editData = { role: '', password: '', can_control: false };
      loadUsers();
    } catch (e) { log(`Update failed: ${e.message}`, 'error'); }
  }
  async function deleteUser(username) {
    if (!confirm(`Delete user '${username}'? This cannot be undone.`)) return;
    try { await api.deleteUser(username); log(`User '${username}' deleted`, 'success'); loadUsers(); }
    catch (e) { log(`Delete failed: ${e.message}`, 'error'); }
  }
</script>

<header class="topbar">
  <div class="brand">
    <div class="brand-mark">M</div>
    <div class="brand-name">MIR&nbsp;Suite<small>Jetson AGX Orin</small></div>
  </div>

  <nav class="tabs">
    {#each tabs as t (t.id)}
      <button class="tab" class:active={view === t.id} onclick={() => onNav?.(t.id)}>
        <span class="tdot"></span>{t.label}
        {#if t.id === 'system'}<span class="tcount">{nodeCount.up}/{nodeCount.total}</span>{/if}
      </button>
    {/each}
  </nav>

  <div class="top-right">
    <div class="conn" class:off={!rosState.connected} title="rosbridge status">
      <span class="pulse" class:on={rosState.connected}></span>
      <span class="conn-lbl">{rosState.connected ? 'rosbridge' : 'offline'}</span>
    </div>

    <button class="iconbtn" onclick={toggleTheme} title="Toggle light / dark" aria-label="Toggle theme">
      {#if dark}
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/></svg>
      {:else}
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>
      {/if}
    </button>

    <div class="user-wrap">
      <button class="user" onclick={() => (showMenu = !showMenu)}>
        <span class="avatar">{initial}</span>
        <span class="user-meta">
          <span class="un">{profile.username || '—'}</span>
          <span class="ur">{profile.role}{canControl() ? '' : ' · read-only'}</span>
        </span>
        <svg class="chev" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>
      </button>
      {#if showMenu}
        <div class="menu-backdrop" onclick={() => (showMenu = false)}></div>
        <div class="menu">
          {#if profile.role === 'admin'}
            <button class="menu-item" onclick={openManage}>Manage users</button>
            <button class="menu-item" onclick={() => { showCreate = true; showMenu = false; }}>Create user</button>
            <div class="menu-sep"></div>
          {/if}
          <button class="menu-item danger" onclick={logout}>Sign out</button>
        </div>
      {/if}
    </div>
  </div>
</header>

{#if showCreate}
  <div class="overlay" onclick={() => (showCreate = false)}>
    <div class="modal" onclick={(e) => e.stopPropagation()}>
      <h3>Create user</h3>
      <label>Username<input bind:value={nu.username} placeholder="e.g. maria" autocomplete="off" /></label>
      <label>Password<input type="password" bind:value={nu.password} autocomplete="new-password" /></label>
      <label>Role
        <select bind:value={nu.role}>
          <option value="user">user</option>
          <option value="admin">admin</option>
        </select>
      </label>
      <label class="chk" class:disabled={nu.role === 'admin'}>
        <input type="checkbox" bind:checked={nu.can_control} disabled={nu.role === 'admin'} />
        Can control hardware (move arms, start/stop driver &amp; nodes)
      </label>
      {#if nu.role === 'admin'}<span class="hint">Admins can always control.</span>{/if}
      <div class="modal-actions">
        <button onclick={() => (showCreate = false)}>Cancel</button>
        <button class="btn-accent" onclick={createUser} disabled={creating || !nu.username.trim() || !nu.password}>Create</button>
      </div>
    </div>
  </div>
{/if}

{#if showManage}
  <div class="overlay" onclick={() => (showManage = false)}>
    <div class="modal users-modal" onclick={(e) => e.stopPropagation()}>
      <h3>Manage users</h3>
      <div class="users-list">
        {#each users as user}
          <div class="user-item">
            {#if editingUser === user.username}
              <div class="edit-form">
                <span class="username">{user.username}</span>
                <label>Role
                  <select bind:value={editData.role}>
                    <option value="user">user</option>
                    <option value="admin">admin</option>
                  </select>
                </label>
                <label>Password <span class="hint">(leave empty to keep)</span>
                  <input type="password" bind:value={editData.password} autocomplete="new-password" placeholder="new password" />
                </label>
                <label class="chk" class:disabled={editData.role === 'admin'}>
                  <input type="checkbox" bind:checked={editData.can_control} disabled={editData.role === 'admin'} />
                  Can control hardware
                </label>
                {#if editData.role === 'admin'}<span class="hint">Admins can always control.</span>{/if}
                <div class="edit-actions">
                  <button onclick={() => (editingUser = null)}>Cancel</button>
                  <button class="btn-accent" onclick={saveEdit}>Save</button>
                </div>
              </div>
            {:else}
              <span class="username">{user.username}</span>
              <span class="role-badge">{user.role}</span>
              {#if user.role === 'admin' || user.can_control}
                <span class="ctrl-badge" title="May actuate hardware">control</span>
              {:else}
                <span class="ctrl-badge ro" title="Read-only: cannot actuate hardware">read-only</span>
              {/if}
              <div class="user-actions">
                <button onclick={() => startEdit(user)}>Edit</button>
                <button class="btn-danger" onclick={() => deleteUser(user.username)} disabled={user.username === profile.username}>Delete</button>
              </div>
            {/if}
          </div>
        {/each}
      </div>
      <div class="modal-actions">
        <button onclick={() => (showManage = false)}>Close</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .topbar {
    position: sticky; top: 0; z-index: 20;
    display: flex; align-items: center; gap: 18px;
    height: 56px; padding: 0 18px;
    background: color-mix(in srgb, var(--panel) 88%, transparent);
    backdrop-filter: blur(10px);
    border-bottom: 1px solid var(--border);
  }
  .brand { display: flex; align-items: center; gap: 10px; flex: none; }
  .brand-mark {
    width: 26px; height: 26px; border-radius: 7px; flex: none;
    background: linear-gradient(135deg, var(--brand), var(--accent));
    display: grid; place-items: center; color: #fff; font-weight: 800; font-size: 13px;
    box-shadow: 0 2px 8px rgba(78, 0, 142, 0.35);
  }
  .brand-name { font-weight: 700; letter-spacing: -0.02em; font-size: 15px; color: var(--heading); display: flex; align-items: baseline; gap: 6px; }
  .brand-name small { color: var(--faint); font-weight: 500; font-size: 11px; }
  @media (max-width: 720px) { .brand-name small { display: none; } }

  .tabs { display: flex; gap: 2px; flex: 1; overflow-x: auto; scrollbar-width: none; }
  .tabs::-webkit-scrollbar { display: none; }
  .tab {
    border: 0; background: transparent; color: var(--muted);
    padding: 7px 13px; border-radius: 8px; font-weight: 550; font-size: 13.5px;
    display: flex; align-items: center; gap: 7px; white-space: nowrap;
  }
  .tab:hover { background: var(--panel-2); color: var(--text); }
  .tab.active { background: var(--accent-soft); color: var(--accent); }
  .tab .tdot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; opacity: 0.45; }
  .tab.active .tdot { opacity: 1; }
  .tab .tcount { font-family: var(--mono); font-size: 11px; padding: 0 6px; border-radius: 20px; background: var(--panel-3); color: var(--muted); font-weight: 600; }

  .top-right { display: flex; align-items: center; gap: 10px; flex: none; }
  .conn {
    display: flex; align-items: center; gap: 7px; font-size: 12.5px; color: var(--muted);
    padding: 5px 11px; border-radius: 20px; border: 1px solid var(--border); background: var(--panel-2);
  }
  .conn.off { color: var(--err); border-color: color-mix(in srgb, var(--err) 35%, transparent); }
  @media (max-width: 800px) { .conn-lbl { display: none; } }
  .pulse { width: 8px; height: 8px; border-radius: 50%; background: var(--err); }
  .pulse.on { background: var(--ok); box-shadow: 0 0 0 0 var(--ok); animation: pulse 2s infinite; }
  @keyframes pulse {
    0% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--ok) 55%, transparent); }
    70% { box-shadow: 0 0 0 6px transparent; }
    100% { box-shadow: 0 0 0 0 transparent; }
  }
  @media (prefers-reduced-motion: reduce) { .pulse.on { animation: none; } }

  .iconbtn { width: 34px; height: 34px; border-radius: 8px; border: 1px solid var(--border); background: var(--panel-2); color: var(--muted); display: grid; place-items: center; padding: 0; }
  .iconbtn:hover { color: var(--text); border-color: var(--border-strong); }

  .user-wrap { position: relative; }
  .user { display: flex; align-items: center; gap: 8px; padding: 4px 8px 4px 5px; border-radius: 10px; border: 1px solid transparent; background: transparent; }
  .user:hover { background: var(--panel-2); border-color: var(--border); }
  .avatar { width: 30px; height: 30px; border-radius: 8px; background: var(--panel-3); display: grid; place-items: center; font-weight: 700; font-size: 12px; color: var(--accent); border: 1px solid var(--border); }
  .user-meta { line-height: 1.2; text-align: left; display: flex; flex-direction: column; }
  .user-meta .un { font-weight: 600; font-size: 13px; color: var(--heading); }
  .user-meta .ur { font-size: 11px; color: var(--faint); }
  .user .chev { color: var(--faint); }
  @media (max-width: 640px) { .user-meta { display: none; } }

  .menu-backdrop { position: fixed; inset: 0; z-index: 30; }
  .menu {
    position: absolute; right: 0; top: calc(100% + 8px); z-index: 31; min-width: 180px;
    background: var(--panel); border: 1px solid var(--border); border-radius: 10px;
    box-shadow: var(--shadow); padding: 6px; display: flex; flex-direction: column; gap: 2px;
  }
  .menu-item { text-align: left; background: transparent; border: 0; padding: 8px 10px; border-radius: 7px; font-size: 13px; color: var(--text); }
  .menu-item:hover { background: var(--panel-2); }
  .menu-item.danger { color: var(--err); }
  .menu-sep { height: 1px; background: var(--border); margin: 4px 2px; }

  .overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.55); display: flex; align-items: center; justify-content: center; z-index: 50; }
  .modal { background: var(--panel); border: 1px solid var(--border); border-radius: 12px; padding: 20px; width: 340px; display: flex; flex-direction: column; gap: 12px; box-shadow: var(--shadow); }
  .users-modal { width: 520px; max-height: 80vh; overflow-y: auto; }
  .modal h3 { font-size: 15px; }
  .modal label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--muted); }
  .modal input, .modal select { font-size: 13px; }
  .modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 4px; }
  .users-list { display: flex; flex-direction: column; gap: 8px; margin: 8px 0; }
  .user-item { display: flex; align-items: center; gap: 10px; padding: 10px; background: var(--panel-2); border-radius: 8px; border: 1px solid var(--border); }
  .user-item .username { font-weight: 600; color: var(--heading); flex: 1; }
  .role-badge { font-size: 11px; padding: 2px 8px; border-radius: 10px; background: var(--accent); color: #fff; font-weight: 600; }
  .ctrl-badge { font-family: var(--mono); font-size: 10px; padding: 2px 8px; border-radius: 10px; font-weight: 600; color: var(--ok); background: var(--ok-soft); border: 1px solid color-mix(in srgb, var(--ok) 30%, transparent); }
  .ctrl-badge.ro { color: var(--muted); background: var(--panel-3); border-color: var(--border); }
  .chk { flex-direction: row !important; align-items: center; gap: 8px; font-size: 12px; color: var(--text); }
  .chk input { width: auto; }
  .chk.disabled { opacity: 0.5; }
  .user-actions { display: flex; gap: 6px; }
  .user-actions button { font-size: 11px; padding: 4px 8px; }
  .edit-form { display: flex; flex-direction: column; gap: 8px; width: 100%; }
  .edit-form .username { font-weight: 600; color: var(--heading); margin-bottom: 4px; }
  .edit-form label { font-size: 11px; }
  .edit-form input, .edit-form select { font-size: 12px; padding: 6px 8px; }
  .edit-actions { display: flex; justify-content: flex-end; gap: 6px; margin-top: 4px; }
  .edit-actions button { font-size: 11px; padding: 4px 10px; }
  .hint { font-size: 10px; opacity: 0.7; font-style: italic; }
</style>
