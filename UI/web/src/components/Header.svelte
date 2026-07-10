<script>
  import { rosState } from '../lib/ros.svelte.js';
  import { logout } from '../lib/auth.svelte.js';
  import { profile, canControl } from '../lib/profiles.svelte.js';
  import { api } from '../lib/api.js';
  import { log } from '../lib/log.svelte.js';

  let showCreate = $state(false);
  let showManage = $state(false);
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
    try {
      const r = await api.listUsers();
      users = r?.users || [];
    } catch (e) {
      log(`Failed to load users: ${e.message}`, 'error');
    }
  }

  function openManage() {
    showManage = true;
    loadUsers();
  }

  function startEdit(user) {
    editingUser = user.username;
    editData = { role: user.role, password: '', can_control: !!user.can_control };
  }

  async function saveEdit() {
    if (!editingUser) return;
    try {
      const updates = { role: editData.role, can_control: editData.can_control };
      if (editData.password) updates.password = editData.password;
      await api.updateUser(editingUser, updates);
      log(`User '${editingUser}' updated`, 'success');
      editingUser = null;
      editData = { role: '', password: '' };
      loadUsers();
    } catch (e) {
      log(`Update failed: ${e.message}`, 'error');
    }
  }

  async function deleteUser(username) {
    if (!confirm(`Delete user '${username}'? This cannot be undone.`)) return;
    try {
      await api.deleteUser(username);
      log(`User '${username}' deleted`, 'success');
      loadUsers();
    } catch (e) {
      log(`Delete failed: ${e.message}`, 'error');
    }
  }
</script>

<header class="app-header">
  <div class="title">
    <h1>MIR Suite</h1>
    <span class="sub">
      {#if profile.username}
        {profile.username}<span class="role">· {profile.role}</span>
        {#if !canControl()}
          <span class="ro-flag" title="Your account cannot actuate hardware. Ask an admin to grant 'Can control'.">read-only</span>
        {/if}
      {:else}
        Kevin · Jetson AGX Orin
      {/if}
    </span>
  </div>
  <div class="right">
    <div class="conn" title="rosbridge status">
      <span class="dot" class:on={rosState.connected}></span>
      <span>{rosState.connected ? 'Connected' : 'Disconnected'}</span>
    </div>
    {#if profile.role === 'admin'}
      <button class="manage" onclick={openManage}>Manage users</button>
      <button onclick={() => (showCreate = true)}>Create user</button>
    {/if}
    <button class="logout" onclick={logout}>Sign out</button>
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
  .app-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 20px;
    background: var(--panel);
    border-bottom: 1px solid var(--border);
  }
  .title { display: flex; align-items: baseline; gap: 12px; }
  h1 { font-size: 18px; color: #fff; letter-spacing: 0.02em; }
  .sub { color: var(--muted); font-size: 12px; }
  .role { margin-left: 4px; opacity: 0.8; }
  .ro-flag {
    margin-left: 8px; font-size: 10px; padding: 1px 7px; border-radius: 10px;
    background: rgba(224,164,78,0.15); color: #e0a44e; border: 1px solid rgba(224,164,78,0.4);
    font-weight: 600;
  }
  .right { display: flex; align-items: center; gap: 14px; }
  .conn { display: flex; align-items: center; gap: 8px; color: var(--muted); font-size: 13px; }
  .dot { width: 9px; height: 9px; border-radius: 50%; background: var(--err); transition: background 0.2s; }
  .dot.on { background: var(--ok); }
  .manage { font-size: 12px; padding: 5px 10px; }
  .logout { font-size: 12px; padding: 5px 10px; }

  .overlay {
    position: fixed; inset: 0; background: rgba(0,0,0,0.55);
    display: flex; align-items: center; justify-content: center; z-index: 50;
  }
  .modal {
    background: var(--panel); border: 1px solid var(--border); border-radius: 10px;
    padding: 20px; width: 320px; display: flex; flex-direction: column; gap: 12px;
  }
  .users-modal { width: 500px; max-height: 80vh; overflow-y: auto; }
  .modal h3 { color: #fff; font-size: 15px; }
  .modal label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--muted); }
  .modal input, .modal select { padding: 7px 9px; font-size: 13px; }
  .modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 4px; }
  
  .users-list { display: flex; flex-direction: column; gap: 8px; margin: 8px 0; }
  .user-item {
    display: flex; align-items: center; gap: 10px; padding: 10px;
    background: rgba(0,0,0,0.2); border-radius: 6px; border: 1px solid var(--border);
  }
  .user-item .username { font-weight: 600; color: #fff; flex: 1; }
  .role-badge {
    font-size: 11px; padding: 2px 8px; border-radius: 10px;
    background: var(--tampere-2); color: #000; font-weight: 600;
  }
  .ctrl-badge {
    font-size: 10px; padding: 2px 8px; border-radius: 10px; font-weight: 600;
    background: rgba(46,158,79,0.18); color: #2e9e4f; border: 1px solid rgba(46,158,79,0.4);
  }
  .ctrl-badge.ro { background: rgba(255,255,255,0.06); color: var(--muted); border-color: var(--border); }
  .chk { flex-direction: row !important; align-items: center; gap: 8px; font-size: 12px; color: var(--text); }
  .chk input { width: auto; }
  .chk.disabled { opacity: 0.5; }
  .user-actions { display: flex; gap: 6px; }
  .user-actions button { font-size: 11px; padding: 4px 8px; }
  .btn-danger { background: var(--err); color: #fff; border: 1px solid var(--err); }
  .btn-danger:disabled { opacity: 0.4; cursor: not-allowed; }
  
  .edit-form { display: flex; flex-direction: column; gap: 8px; width: 100%; }
  .edit-form .username { font-weight: 600; color: #fff; margin-bottom: 4px; }
  .edit-form label { font-size: 11px; }
  .edit-form input, .edit-form select { font-size: 12px; padding: 6px 8px; }
  .edit-actions { display: flex; justify-content: flex-end; gap: 6px; margin-top: 4px; }
  .edit-actions button { font-size: 11px; padding: 4px 10px; }
  .hint { font-size: 10px; opacity: 0.7; font-style: italic; }
</style>
