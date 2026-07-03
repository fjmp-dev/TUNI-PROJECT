<script>
  // Real-time 3D viewer of both UR5e arms, built as primitives (cylinders for
  // links, spheres for joints) following ur5e_chain.json — the kinematic chain
  // from the URDF. We use primitives instead of the .dae meshes because the
  // ColladaLoader geometry refused to render (valid verts but invisible), while
  // the chain transforms themselves are correct.
  //
  // Per the project constraint, joints are shown AS REPORTED: the model uses the
  // URDF orientation; the physical arms are mounted reversed, so this is a joint
  // visualization, not a twin of the real-world orientation.
  import { onMount, onDestroy } from 'svelte';
  import * as THREE from 'three';
  import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
  import { jointsState, startJoints, stopJoints } from '../lib/joints.svelte.js';
  import { log } from '../lib/log.svelte.js';

  let container;
  let webglError = $state(false);
  let loading = $state(true);

  let scene, camera, renderer, controls, raf;
  const arms = {};
  const framables = [];
  // Simulated torso geometry (does not exist physically; for presentation).
  const SHOULDER_X = 0.30, SHOULDER_Y = 0.5;

  const setRpy = (obj, rpy) => {
    obj.rotation.order = 'XYZ';
    obj.rotation.set(rpy[0], rpy[1], rpy[2]);
  };

  // A simple simulated body so the arms read as a coherent robot. None of this
  // exists physically — it's only a presentation aid (a box "MiR" base, a torso
  // column, and shoulder caps the arms emerge from).
  function buildTorso() {
    const bodyMat = new THREE.MeshStandardMaterial({ color: 0x2b2e38, metalness: 0.2, roughness: 0.7 });
    const baseMat = new THREE.MeshStandardMaterial({ color: 0x1b1d24, metalness: 0.2, roughness: 0.85 });
    const torso = new THREE.Group();

    const base = new THREE.Mesh(new THREE.BoxGeometry(0.66, 0.06, 0.4), baseMat);
    base.position.y = 0.03;
    torso.add(base);

    const body = new THREE.Mesh(new THREE.BoxGeometry(0.48, 0.46, 0.22), bodyMat);
    body.position.y = 0.29;
    torso.add(body);

    for (const sx of [-SHOULDER_X, SHOULDER_X]) {
      const cap = new THREE.Mesh(new THREE.SphereGeometry(0.05, 16, 12), bodyMat);
      cap.position.set(sx, SHOULDER_Y, 0);
      torso.add(cap);
    }
    scene.add(torso);
    framables.push(torso);
  }

  function buildArm(side, chain) {
    const armGroup = new THREE.Group();
    // Chain is in ROS coords (Z up); rotate so Z-up maps to Three.js Y-up.
    armGroup.rotation.x = -Math.PI / 2;

    const linkMat = new THREE.MeshStandardMaterial({ color: 0x8d9199, metalness: 0.3, roughness: 0.55 });
    const jointMat = new THREE.MeshStandardMaterial({
      color: side === 'left' ? 0x4e9be0 : 0xe08a4e,
      metalness: 0.2,
      roughness: 0.5,
    });

    // Base marker.
    const base = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.07, 0.04, 20), linkMat);
    base.frustumCulled = false;
    armGroup.add(base);

    const jointInfos = {};
    let parent = armGroup;
    for (const step of chain.chain) {
      // Rigid link from the parent joint to this one (the fixed offset).
      const off = new THREE.Vector3(...step.origin_xyz);
      if (off.length() > 1e-4) {
        const link = new THREE.Mesh(new THREE.CylinderGeometry(0.028, 0.028, off.length(), 14), linkMat);
        link.frustumCulled = false;
        link.position.copy(off).multiplyScalar(0.5);
        link.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), off.clone().normalize());
        parent.add(link);
      }

      const jg = new THREE.Group();
      jg.name = step.joint_name;
      jg.position.copy(off);
      setRpy(jg, step.origin_rpy);
      parent.add(jg);

      const marker = new THREE.Mesh(new THREE.SphereGeometry(0.045, 16, 12), jointMat);
      marker.frustumCulled = false;
      jg.add(marker);

      jointInfos[step.joint_name] = { group: jg, initialRpy: [...step.origin_rpy] };
      parent = jg;
    }

    // Mount on a simulated shoulder and yaw so the arm reaches FORWARD (+Z)
    // instead of sideways. Presentation only — the real arms face the MiR's back.
    const mount = new THREE.Group();
    mount.position.set(side === 'left' ? -SHOULDER_X : SHOULDER_X, SHOULDER_Y, 0);
    mount.rotation.y = -Math.PI / 2;
    // Mirror the right arm across the sagittal plane so the pair is symmetric
    // (both reaching forward). The mirror flips Z-rotation handedness, so live
    // joint angles are negated for the right arm in updatePoses.
    if (side === 'right') mount.scale.x = -1;
    mount.add(armGroup);
    scene.add(mount);
    arms[side] = jointInfos;
    framables.push(mount);
  }

  // All UR5e joints rotate about their local Z (URDF axis 0 0 1).
  function updatePoses(names, positions) {
    if (!names || !positions) return;
    for (let i = 0; i < names.length; i++) {
      const full = names[i];
      const side = full.startsWith('left_') ? 'left' : full.startsWith('right_') ? 'right' : null;
      if (!side || !arms[side]) continue;
      const entry = arms[side][full.replace(/^(left_|right_)/, '')];
      if (!entry) continue;
      entry.group.rotation.set(...entry.initialRpy);
      // Right arm is mirrored (mount.scale.x = -1), so negate to keep rotation sense.
      entry.group.rotateZ((side === 'right' ? -1 : 1) * positions[i]);
    }
  }

  $effect(() => {
    const d = jointsState.data;
    if (d) updatePoses(d.names, d.position);
  });

  function frameCamera() {
    scene.updateMatrixWorld(true);
    const box = new THREE.Box3();
    for (const g of framables) box.expandByObject(g);
    if (box.isEmpty() || !isFinite(box.min.x)) return;
    const sphere = box.getBoundingSphere(new THREE.Sphere());
    const center = sphere.center;
    const r = Math.max(sphere.radius, 0.1);
    // Distance that fits the bounding sphere in the vertical FOV, with margin.
    const dist = (r / Math.sin((camera.fov * Math.PI) / 360)) * 1.15;
    const dir = new THREE.Vector3(0.8, 0.5, 1).normalize();
    camera.position.copy(center).addScaledVector(dir, dist);
    camera.near = dist / 100;
    camera.far = dist * 100;
    camera.updateProjectionMatrix();
    controls.target.copy(center);
    controls.update();
  }

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
    camera = new THREE.PerspectiveCamera(45, 2, 0.01, 50);
    camera.position.set(1.2, 0.9, 1.4);

    scene.add(new THREE.AmbientLight(0x909090, 2.0));
    const key = new THREE.DirectionalLight(0xffffff, 1.6);
    key.position.set(1, 2, 1);
    scene.add(key);
    const fill = new THREE.DirectionalLight(0x6666aa, 0.6);
    fill.position.set(-1, 0.5, -1);
    scene.add(fill);
    scene.add(new THREE.GridHelper(2, 20, 0x4e008e, 0x2a2730));

    container.appendChild(renderer.domElement);
    controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.1;

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
      buildTorso();
      buildArm('left', chain);
      buildArm('right', chain);
      frameCamera();
      log('3D viewer: arms built', 'success');
    } catch (e) {
      log('3D viewer: error building arms: ' + e.message, 'error');
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
    <h2>3D Viewer — UR5e</h2>
    <span class="badge" class:ok={!loading && !webglError}>
      {webglError ? 'WebGL unavailable' : loading ? 'loading…' : 'live'}
    </span>
  </div>
  <div class="panel-body">
    <div class="view" bind:this={container}>
      {#if webglError}
        <div class="msg">This browser has no WebGL available.</div>
      {/if}
    </div>
    <div class="hint">
      Live joints (left = blue, right = orange). Shown on a simulated body — the physical arms are mounted facing the MiR's back.
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
