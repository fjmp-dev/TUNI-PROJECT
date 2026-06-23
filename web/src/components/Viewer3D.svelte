<script>
  // Real-time 3D viewer of both UR5e arms. Ported from the legacy robot3d.js:
  // loads ur5e_chain.json (kinematic chain from the URDF) + the .dae meshes and
  // animates each joint from /api/ur/joints.
  //
  // Per the project constraint, joints are shown AS REPORTED. The model uses the
  // URDF orientation; the physical arms are mounted facing backward, so the model
  // is a joint visualization, NOT a twin of the real-world orientation.
  import { onMount, onDestroy } from 'svelte';
  import * as THREE from 'three';
  import { ColladaLoader } from 'three/addons/loaders/ColladaLoader.js';
  import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
  import { jointsState, startJoints, stopJoints } from '../lib/joints.svelte.js';
  import { log } from '../lib/log.svelte.js';

  const MESH_MAP = {
    'base.dae': 'ur5e_base.dae',
    'shoulder.dae': 'ur5e_shoulder.dae',
    'upperarm.dae': 'ur5e_upperarm.dae',
    'forearm.dae': 'ur5e_forearm.dae',
    'wrist1.dae': 'ur5e_wrist1.dae',
    'wrist2.dae': 'ur5e_wrist2.dae',
    'wrist3.dae': 'ur5e_wrist3.dae',
  };

  let container;
  let webglError = $state(false);
  let loading = $state(true);

  let scene, camera, renderer, controls, raf;
  const arms = {};
  const loader = new ColladaLoader();

  const setRpy = (obj, rpy) => {
    obj.rotation.order = 'XYZ';
    obj.rotation.set(rpy[0], rpy[1], rpy[2]);
  };

  async function loadCollada(url) {
    const collada = await loader.loadAsync(url);
    return collada.scene;
  }

  async function loadArm(side, chain) {
    const armGroup = new THREE.Group();
    armGroup.position.set(side === 'left' ? -0.35 : 0.35, 0, 0);

    if (chain.base) {
      const f = MESH_MAP[chain.base.visual_mesh];
      if (f) {
        const m = await loadCollada('/models/' + f);
        setRpy(m, chain.base.visual_rpy);
        m.position.set(...chain.base.visual_xyz);
        armGroup.add(m);
      }
    }

    const jointInfos = {};
    let parent = armGroup;
    for (const step of chain.chain) {
      const jg = new THREE.Group();
      jg.name = step.joint_name;
      jg.position.set(...step.origin_xyz);
      setRpy(jg, step.origin_rpy);
      parent.add(jg);

      const mf = MESH_MAP[step.visual_mesh];
      if (mf) {
        const m = await loadCollada('/models/' + mf);
        setRpy(m, step.visual_rpy);
        m.position.set(...step.visual_xyz);
        jg.add(m);
      }
      jointInfos[step.joint_name] = { group: jg, initialRpy: [...step.origin_rpy] };
      parent = jg;
    }

    scene.add(armGroup);
    arms[side] = jointInfos;
  }

  // Apply joint angles. All UR5e joints rotate about local Z (URDF axis 0 0 1).
  function updatePoses(names, positions) {
    if (!names || !positions) return;
    for (let i = 0; i < names.length; i++) {
      const full = names[i];
      const side = full.startsWith('left_') ? 'left' : full.startsWith('right_') ? 'right' : null;
      if (!side || !arms[side]) continue;
      const entry = arms[side][full.replace(/^(left_|right_)/, '')];
      if (!entry) continue;
      entry.group.rotation.set(...entry.initialRpy);
      entry.group.rotateZ(positions[i]);
    }
  }

  $effect(() => {
    const d = jointsState.data;
    if (d) updatePoses(d.names, d.position);
  });

  function resize() {
    if (!renderer || !container) return;
    const w = container.clientWidth;
    const h = container.clientHeight || 360;
    renderer.setSize(w, h);
    camera.aspect = w / Math.max(h, 1);
    camera.updateProjectionMatrix();
  }

  onMount(async () => {
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true });
    } catch (e) {
      webglError = true;
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));

    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x14131a);
    camera = new THREE.PerspectiveCamera(45, 2, 0.05, 20);
    camera.position.set(1.4, 0.9, 1.6);

    scene.add(new THREE.AmbientLight(0x909090, 2.0));
    const key = new THREE.DirectionalLight(0xffffff, 1.5);
    key.position.set(1, 2, 1);
    scene.add(key);
    const fill = new THREE.DirectionalLight(0x6666aa, 0.5);
    fill.position.set(-1, 0.3, -1);
    scene.add(fill);
    scene.add(new THREE.GridHelper(2, 20, 0x4e008e, 0x2a2730));

    container.appendChild(renderer.domElement);
    controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(0, 0.3, 0);
    controls.enableDamping = true;
    controls.dampingFactor = 0.1;
    controls.update();

    resize();
    window.addEventListener('resize', resize);

    const animate = () => {
      raf = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    try {
      const chain = await (await fetch('/models/ur5e_chain.json')).json();
      await loadArm('left', chain);
      await loadArm('right', chain);
      log('Visor 3D: brazos cargados', 'success');
    } catch (e) {
      log('Visor 3D: error cargando mallas: ' + e.message, 'error');
    } finally {
      loading = false;
    }

    startJoints();
  });

  onDestroy(() => {
    stopJoints();
    cancelAnimationFrame(raf);
    window.removeEventListener('resize', resize);
    renderer?.dispose?.();
  });
</script>

<div class="panel">
  <div class="panel-header">
    <h2>Visor 3D — UR5e</h2>
    <span class="badge" class:ok={!loading && !webglError}>
      {webglError ? 'WebGL no disponible' : loading ? 'cargando…' : 'en vivo'}
    </span>
  </div>
  <div class="panel-body">
    <div class="view" bind:this={container}>
      {#if webglError}
        <div class="msg">Este navegador no tiene WebGL disponible.</div>
      {/if}
    </div>
    <div class="hint">
      Joints en vivo. El modelo usa la orientación del URDF; el montaje físico real va al revés.
    </div>
  </div>
</div>

<style>
  .view {
    height: 360px;
    background: #000;
    border-radius: 6px;
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .view :global(canvas) { display: block; }
  .msg { color: var(--warn); font-size: 13px; padding: 16px; text-align: center; }
  .hint { margin-top: 8px; font-size: 12px; color: var(--muted); }
</style>
