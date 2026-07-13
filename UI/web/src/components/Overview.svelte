<script>
  import { onMount, onDestroy } from 'svelte';
  import { api } from '../lib/api.js';
  import { rosState } from '../lib/ros.svelte.js';
  import { jointsState, startJoints, stopJoints } from '../lib/joints.svelte.js';
  import { nodesState, startNodes, stopNodes } from '../lib/nodes.svelte.js';
  import { profile, canControl } from '../lib/profiles.svelte.js';
  import { busy, startNode, stopNode, startMyNodes } from '../lib/nodeControl.svelte.js';

  let { onNav } = $props();

  const joints = $derived(jointsState.data);
  const JOINTS = [
    ['shoulder_pan_joint', 'shoulder_pan'], ['shoulder_lift_joint', 'shoulder_lift'],
    ['elbow_joint', 'elbow'], ['wrist_1_joint', 'wrist_1'],
    ['wrist_2_joint', 'wrist_2'], ['wrist_3_joint', 'wrist_3'],
  ];
  const fmt = (v) => (v == null ? '—' : v.toFixed(3));
  // Map a joint radian value (~ -pi..pi) to a 0..100 bar fill.
  const barPct = (v) => (v == null ? 0 : Math.max(2, Math.min(100, ((v + Math.PI) / (2 * Math.PI)) * 100)));

  // ---- MiR + force: light own polls (Overview only) ----
  let mir = $state(null);
  let mirOffline = $state(false);
  let force = $state({ left: null, right: null });
  let mirTimer, forceTimer;
  const mag = (s) => (s ? Math.hypot(s.fx || 0, s.fy || 0, s.fz || 0) : null);

  async function pollMir() {
    try { mir = await api.mirStatus(); mirOffline = false; }
    catch { mirOffline = true; }
  }
  async function pollForce() {
    try { const r = await api.force(); if (r?.sensors) force = r.sensors; } catch {}
  }

  onMount(() => {
    startNodes(); startJoints();
    pollMir(); pollForce();
    mirTimer = setInterval(pollMir, 5000);
    forceTimer = setInterval(pollForce, 700);
  });
  onDestroy(() => {
    stopNodes(); stopJoints();
    clearInterval(mirTimer); clearInterval(forceTimer);
  });

  // ---- derived tile state ----
  const armsActive = $derived(!!(joints && !joints.stale));
  const cameraNode = $derived((nodesState.nodes || []).find((n) => (n.id === 'camera_color' || n.id === 'camera_depth') && n.running));
  const rosUp = $derived(rosState.connected);
  const forceMag = $derived({ left: mag(force.left), right: mag(force.right) });

  const runningNodes = $derived((nodesState.nodes || []).filter((n) => n.running));
  const stoppedNodes = $derived((nodesState.nodes || []).filter((n) => !n.running));

  // ---- rosbag recording ----
  // Surfaced as its own button because a recording that nobody can see is a recording
  // nobody stops: buried in the node list, one left running wrote 522 GB and filled the
  // disk. It is never auto-started (no_autostart in the backend) -- only this click.
  const recording = $derived(!!(nodesState.nodes || []).find((n) => n.id === 'rosbag' && n.running));
  const toggleRec = () => (recording ? stopNode('rosbag') : startNode('rosbag'));
</script>

<div class="view-head">
  <div>
    <div class="eyebrow">Live system state</div>
    <h1>Overview</h1>
    <p>Everything the suite is running right now. Jump into a subsystem from its tab.</p>
  </div>
  <div class="head-actions">
    <button class="btn rec" class:on={recording} onclick={toggleRec}
            disabled={!canControl() || busy['n:rosbag']}
            title={canControl()
              ? (recording ? 'Stop the rosbag recording now' : 'Record a rosbag (stops itself after 10 min; raw images excluded)')
              : 'Read-only: control not allowed'}>
      <span class="dot" class:blink={recording}></span>{recording ? 'Recording — stop' : 'Record'}
    </button>
    <button class="btn accent" onclick={startMyNodes} disabled={!canControl()}
            title={canControl() ? 'Launch the nodes in your profile' : 'Read-only: control not allowed'}>Start my nodes</button>
  </div>
</div>

<div class="tiles">
  <div class="tile" class:ok={rosUp} class:err={!rosUp}>
    <div class="tile-top"><span class="tile-label">rosbridge</span><span class="chip {rosUp ? 'ok' : 'err'}">{rosUp ? 'up' : 'down'}</span></div>
    <div class="tile-value">:9090</div>
    <div class="tile-sub">read-only · whitelisted topics</div>
  </div>

  <button class="tile as-btn" class:ok={armsActive} class:idle={!armsActive} onclick={() => onNav?.('arms')}>
    <div class="tile-top"><span class="tile-label">UR5e arms</span><span class="chip {armsActive ? 'ok' : 'idle'}">{armsActive ? 'driver' : 'stopped'}</span></div>
    <div class="tile-value">{armsActive ? '12' : '—'} <small>joints</small></div>
    <div class="tile-sub">400 Hz · .102 / .103</div>
  </button>

  <button class="tile as-btn" class:ok={mir && !mirOffline} class:idle={mirOffline || !mir} onclick={() => onNav?.('mir')}>
    <div class="tile-top"><span class="tile-label">MiR 200</span><span class="chip {mir && !mirOffline ? 'ok' : 'idle'}">{mirOffline || !mir ? 'offline' : (mir.state || 'up')}</span></div>
    <div class="tile-value">{mir && !mirOffline ? `${mir.battery_pct?.toFixed?.(0) ?? '—'}` : '—'}<small>{mir && !mirOffline ? ' %' : ''}</small></div>
    <div class="tile-sub">{mirOffline || !mir ? 'powered off' : (mir.mode || 'base')}</div>
  </button>

  <button class="tile as-btn" class:warn={cameraNode} class:idle={!cameraNode} onclick={() => onNav?.('camera')}>
    <div class="tile-top"><span class="tile-label">Camera</span><span class="chip {cameraNode ? 'warn' : 'idle'}">{cameraNode ? 'in use' : 'idle'}</span></div>
    <div class="tile-value">{cameraNode ? cameraNode.id.replace('camera_', '') : '—'}</div>
    <div class="tile-sub">Orbbec Gemini 335Lg</div>
  </button>

  <div class="tile" class:ok={forceMag.left != null || forceMag.right != null} class:idle={forceMag.left == null && forceMag.right == null}>
    <div class="tile-top"><span class="tile-label">Force</span><span class="chip {forceMag.left != null || forceMag.right != null ? 'live' : 'idle'}">{forceMag.left != null || forceMag.right != null ? 'live' : 'no data'}</span></div>
    <div class="tile-value">{forceMag.left != null ? forceMag.left.toFixed(0) : '—'} / {forceMag.right != null ? forceMag.right.toFixed(0) : '—'} <small>N</small></div>
    <div class="tile-sub">Nordbo NRS-6200 L/R</div>
  </div>
</div>

<div class="ov-grid">
  <div class="panel">
    <div class="panel-header">
      <h2>Arm telemetry <span class="h-mono">/joint_states · 400 Hz</span></h2>
      <span class="badge {armsActive ? 'live' : ''}">{armsActive ? 'streaming' : 'stopped'}</span>
    </div>
    <div class="panel-body">
      <div class="arm-wrap">
        {#each ['left', 'right'] as arm}
          <div>
            <div class="arm-title"><h3>{arm === 'left' ? 'Left' : 'Right'}</h3><span class="ip">{arm === 'left' ? '192.168.1.102' : '192.168.1.103'}</span></div>
            {#each JOINTS as [key, label]}
              <div class="jrow">
                <span class="jname">{label}</span>
                <span class="jbar"><i style="width:{barPct(joints?.[arm]?.[key])}%"></i></span>
                <span class="jval">{fmt(joints?.[arm]?.[key])}</span>
              </div>
            {/each}
          </div>
        {/each}
      </div>
    </div>
  </div>

  <div class="panel">
    <div class="panel-header"><h2>Force / torque <span class="h-mono">WS :2003</span></h2></div>
    <div class="panel-body">
      <div class="force-row">
        {#each ['left', 'right'] as side}
          {@const m = forceMag[side]}
          {@const pct = m == null ? 0 : Math.min(1, m / 50)}
          <div class="gauge">
            <svg viewBox="0 0 120 70" aria-hidden="true">
              <path d="M10 62 A50 50 0 0 1 110 62" fill="none" stroke="var(--panel-3)" stroke-width="9" stroke-linecap="round"/>
              <path d="M10 62 A50 50 0 0 1 110 62" fill="none" stroke={side === 'left' ? 'var(--live)' : 'var(--ok)'} stroke-width="9" stroke-linecap="round"
                    stroke-dasharray="157" stroke-dashoffset={157 - pct * 157}/>
            </svg>
            <div class="g-num">{m == null ? '—' : m.toFixed(1)}<span class="g-unit"> N</span></div>
            <div class="g-lbl">{side === 'left' ? 'Left' : 'Right'} hand</div>
          </div>
        {/each}
      </div>
    </div>
  </div>
</div>

<div class="panel" style="margin-top:14px">
  <div class="panel-header">
    <h2>Processes</h2>
    <div class="proc-actions">
      <span class="badge ok">{runningNodes.length} running</span>
      <span class="badge">{stoppedNodes.length} stopped</span>
      <button class="link" onclick={() => onNav?.('system')}>Manage →</button>
    </div>
  </div>
  <div class="panel-body proc">
    <div class="grouplabel">Nodes</div>
    {#each nodesState.nodes as n (n.id)}
      <div class="proc-row">
        <span class="pdot" class:on={n.running}></span>
        <span class="pinfo"><span class="pname">{n.label}</span> <span class="pid">{n.id}</span></span>
        <span class="pmeta">{n.running ? 'running' : 'stopped'}</span>
        {#if n.running}
          <button class="btn-danger sm" onclick={() => stopNode(n.id)} disabled={busy['n:' + n.id] || !canControl()} title={canControl() ? 'Stop' : 'Read-only'}>Stop</button>
        {:else}
          <button class="btn-accent sm" onclick={() => startNode(n.id)} disabled={busy['n:' + n.id] || !canControl()} title={canControl() ? 'Start' : 'Read-only'}>Start</button>
        {/if}
      </div>
    {/each}
    <div class="grouplabel" style="margin-top:8px">System (read-only)</div>
    {#each nodesState.system as s (s.id)}
      <div class="proc-row">
        <span class="pdot" class:on={s.running}></span>
        <span class="pinfo"><span class="pname">{s.label}</span></span>
        <span class="pmeta"></span>
        <span class="sys-state" class:up={s.running}>{s.running ? 'up' : 'down'}</span>
      </div>
    {/each}
  </div>
</div>

<style>
  .head-actions { display: flex; gap: 8px; align-items: center; }
  .btn.rec { display: inline-flex; align-items: center; gap: 7px; }
  .btn.rec .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--faint); }
  .btn.rec.on { color: var(--err); border-color: color-mix(in srgb, var(--err) 45%, transparent); background: var(--err-soft); font-weight: 600; }
  .btn.rec.on .dot { background: var(--err); }
  .dot.blink { animation: rec-pulse 1.2s ease-in-out infinite; }
  @keyframes rec-pulse { 50% { opacity: 0.25; } }
  @media (prefers-reduced-motion: reduce) { .dot.blink { animation: none; } }

  .tiles { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-bottom: 18px; }
  @media (max-width: 1080px) { .tiles { grid-template-columns: repeat(2, 1fr); } }
  @media (max-width: 560px) { .tiles { grid-template-columns: 1fr; } }
  .tile {
    background: var(--panel); border: 1px solid var(--border); border-radius: var(--radius);
    padding: 14px 15px; box-shadow: var(--shadow); position: relative; overflow: hidden; text-align: left;
  }
  .tile.as-btn { cursor: pointer; transition: border-color 0.14s, transform 0.08s; font: inherit; color: var(--text); }
  .tile.as-btn:hover { border-color: var(--accent-line); }
  .tile.as-btn:active { transform: translateY(1px); }
  .tile::before { content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 3px; background: var(--faint); }
  .tile.ok::before { background: var(--ok); }
  .tile.warn::before { background: var(--warn); }
  .tile.err::before { background: var(--err); }
  .tile.idle::before { background: var(--faint); }
  .tile-top { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
  .tile-label { font-size: 12.5px; color: var(--muted); font-weight: 600; }
  .tile-value { font-size: 22px; font-weight: 680; letter-spacing: -0.02em; font-family: var(--mono); color: var(--heading); }
  .tile-value small { font-size: 12px; color: var(--muted); font-weight: 500; font-family: var(--sans); }
  .tile-sub { font-size: 12px; color: var(--faint); margin-top: 3px; }

  .chip { font-family: var(--mono); font-size: 10.5px; font-weight: 600; padding: 2px 8px; border-radius: 20px; text-transform: uppercase; letter-spacing: 0.04em; border: 1px solid transparent; }
  .chip.ok { color: var(--ok); background: var(--ok-soft); border-color: color-mix(in srgb, var(--ok) 30%, transparent); }
  .chip.warn { color: var(--warn); background: var(--warn-soft); border-color: color-mix(in srgb, var(--warn) 30%, transparent); }
  .chip.err { color: var(--err); background: var(--err-soft); border-color: color-mix(in srgb, var(--err) 30%, transparent); }
  .chip.idle { color: var(--faint); background: var(--panel-3); }
  .chip.live { color: var(--live); background: var(--live-soft); border-color: color-mix(in srgb, var(--live) 30%, transparent); }

  .h-mono { font-family: var(--mono); font-size: 11.5px; color: var(--faint); font-weight: 500; }

  .ov-grid { display: grid; grid-template-columns: 1.4fr 1fr; gap: 14px; }
  @media (max-width: 940px) { .ov-grid { grid-template-columns: 1fr; } }

  .arm-wrap { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
  @media (max-width: 560px) { .arm-wrap { grid-template-columns: 1fr; } }
  .arm-title { display: flex; align-items: baseline; gap: 8px; margin-bottom: 8px; }
  .arm-title h3 { font-size: 13px; }
  .arm-title .ip { font-family: var(--mono); font-size: 11px; color: var(--faint); }
  .jrow { display: grid; grid-template-columns: 84px 1fr auto; align-items: center; gap: 10px; padding: 4px 0; }
  .jrow + .jrow { border-top: 1px solid color-mix(in srgb, var(--border) 60%, transparent); }
  .jname { font-size: 12px; color: var(--muted); }
  .jbar { height: 4px; border-radius: 3px; background: var(--panel-3); overflow: hidden; }
  .jbar > i { display: block; height: 100%; background: linear-gradient(90deg, var(--accent), var(--live)); border-radius: 3px; }
  .jval { font-family: var(--mono); font-size: 12.5px; font-variant-numeric: tabular-nums; text-align: right; min-width: 58px; color: var(--text); }

  .force-row { display: flex; gap: 16px; }
  .gauge { flex: 1; text-align: center; }
  .gauge svg { width: 100%; max-width: 140px; height: auto; }
  .g-num { font-family: var(--mono); font-size: 20px; font-weight: 680; color: var(--heading); }
  .g-unit { font-size: 12px; color: var(--muted); }
  .g-lbl { font-size: 12px; color: var(--muted); margin-top: 2px; }

  .proc-actions { display: flex; align-items: center; gap: 8px; }
  .link { background: transparent; border: 0; color: var(--accent); font-size: 12.5px; padding: 4px 6px; }
  .link:hover { text-decoration: underline; }
  .proc { display: flex; flex-direction: column; padding-top: 8px; padding-bottom: 8px; }
  .grouplabel { font-family: var(--mono); font-size: 10.5px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--faint); font-weight: 600; margin: 4px 0 2px; }
  .proc-row { display: grid; grid-template-columns: 12px 1fr auto auto; align-items: center; gap: 12px; padding: 9px 0; }
  .proc-row + .proc-row { border-top: 1px solid color-mix(in srgb, var(--border) 55%, transparent); }
  .pdot { width: 9px; height: 9px; border-radius: 50%; background: var(--faint); }
  .pdot.on { background: var(--ok); box-shadow: 0 0 7px color-mix(in srgb, var(--ok) 70%, transparent); }
  .pinfo { min-width: 0; }
  .pname { font-weight: 550; font-size: 13px; color: var(--heading); }
  .pid { font-family: var(--mono); font-size: 11.5px; color: var(--faint); }
  .pmeta { font-family: var(--mono); font-size: 11.5px; color: var(--muted); text-align: right; }
  .sys-state { font-family: var(--mono); font-size: 11.5px; color: var(--faint); text-transform: uppercase; }
  .sys-state.up { color: var(--ok); }
  .btn-accent.sm, .btn-danger.sm { padding: 4px 10px; font-size: 12px; border-radius: 7px; }
</style>
