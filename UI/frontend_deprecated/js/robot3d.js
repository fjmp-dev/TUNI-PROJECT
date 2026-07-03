// ============================================================
// 3D Robot Viewer — Three.js + ColladaLoader + URDF chain JSON
//
// Loads ur5e_chain.json (auto-generated from the URDF by
// parse_urdf.py) to build the exact same kinematic chain that
// RViz renders. No manual offsets — data comes from the URDF.
// ============================================================

import * as THREE from 'three';
import { ColladaLoader } from 'three/addons/loaders/ColladaLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

function log(msg) {
    console.log('[robot3d]', msg);
    const el = document.getElementById('viewer3d-log');
    if (el) {
        el.innerHTML += '\n' + msg;
        el.scrollTop = el.scrollHeight;
    }
}

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x1a1a2e);

const camera = new THREE.PerspectiveCamera(45, 2, 0.05, 10);
camera.position.set(1.2, 0.8, 1.5);
camera.lookAt(0, 0.25, 0);

let renderer = null;
try {
    renderer = new THREE.WebGLRenderer({
        antialias: false,
        powerPreference: 'default',
        failIfMajorPerformanceCaveat: false,
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1));
    log('WebGL OK');
} catch (e) {
    log('WebGL failed: ' + e.message);
}

scene.add(new THREE.AmbientLight(0x606060, 2.0));
const d1 = new THREE.DirectionalLight(0xffffff, 1.5);
d1.position.set(1, 2, 1);
scene.add(d1);
const d2 = new THREE.DirectionalLight(0x444466, 0.6);
d2.position.set(-1, 0.3, -1);
scene.add(d2);
scene.add(new THREE.GridHelper(2, 20, 0x333355, 0x1a1a2e));

const colladaLoader = new ColladaLoader();

// Arm store: { left: { jointInfos: { joint_name: {group, initialRpy} } }, right: ... }
const arms = {};

// ============================================================
// Helpers
// ============================================================

function setRpy(obj, rpy) {
    obj.rotation.order = 'XYZ';
    obj.rotation.set(rpy[0], rpy[1], rpy[2]);
}

// Map URDF mesh name to our filenames
const MESH_MAP = {
    'base.dae':      'ur5e_base.dae',
    'shoulder.dae':  'ur5e_shoulder.dae',
    'upperarm.dae':  'ur5e_upperarm.dae',
    'forearm.dae':   'ur5e_forearm.dae',
    'wrist1.dae':    'ur5e_wrist1.dae',
    'wrist2.dae':    'ur5e_wrist2.dae',
    'wrist3.dae':    'ur5e_wrist3.dae',
};

// ============================================================
// PUBLIC
// ============================================================

export function initViewer(containerId) {
    const container = document.getElementById(containerId);
    if (!container) { log('ERROR: container ' + containerId); return; }

    if (!renderer) {
        container.innerHTML = '<div style="color:#f80;padding:20px;text-align:center;margin-top:200px;">'
            + '<p style="font-size:18px;">WebGL not available</p>'
            + '<p style="font-size:12px;color:#666;">Try Firefox or Chromium .deb with GPU flags.</p>'
            + '</div>';
        return;
    }

    container.appendChild(renderer.domElement);

    function onResize() {
        const w = container.clientWidth;
        const h = container.clientHeight || 500;
        renderer.setSize(w, h);
        camera.aspect = w / Math.max(h, 1);
        camera.updateProjectionMatrix();
    }
    window.addEventListener('resize', onResize);
    onResize();

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(0, 0.3, 0);
    controls.enableDamping = true;
    controls.dampingFactor = 0.1;
    controls.update();

    function animate() {
        requestAnimationFrame(animate);
        controls.update();
        renderer.render(scene, camera);
    }
    animate();

    log('Viewer initialized');
}

// ============================================================
// PUBLIC: Build an arm from ur5e_chain.json
//   side = 'left' | 'right'
//   baseUrl = '/static/models'  (base path for mesh files)
// ============================================================
export async function loadArm(side) {
    const resp = await fetch('/static/models/ur5e_chain.json');
    const chainData = await resp.json();

    const armGroup = new THREE.Group();
    armGroup.position.set(side === 'left' ? -0.3 : 0.3, 0, 0);

    // --- Base mesh (static, no joint) ---
    if (chainData.base) {
        const baseUrl = MESH_MAP[chainData.base.visual_mesh];
        if (baseUrl) {
            const baseMesh = await loadCollada('/static/models/' + baseUrl);
            setRpy(baseMesh, chainData.base.visual_rpy);
            baseMesh.position.set(...chainData.base.visual_xyz);
            armGroup.add(baseMesh);
        }
    }

    // --- Kinematic chain ---
    const jointInfos = {};
    let parentGroup = armGroup;

    for (const step of chainData.chain) {
        const jg = new THREE.Group();
        jg.name = step.joint_name;
        jg.position.set(...step.origin_xyz);
        parentGroup.add(jg);

        // Apply the joint-origin rpy (this rotates the child frame)
        setRpy(jg, step.origin_rpy);

        // Load and position the visual mesh for this link
        const meshFile = MESH_MAP[step.visual_mesh];
        if (meshFile) {
            const mesh = await loadCollada('/static/models/' + meshFile);
            setRpy(mesh, step.visual_rpy);
            mesh.position.set(...step.visual_xyz);
            jg.add(mesh);
        }

        jointInfos[step.joint_name] = {
            group: jg,
            initialRpy: [...step.origin_rpy],
        };

        parentGroup = jg;
    }

    scene.add(armGroup);
    arms[side] = jointInfos;
    log(side + ' arm: ' + Object.keys(jointInfos).length + ' joints');
}

async function loadCollada(url) {
    const collada = await colladaLoader.loadAsync(url);
    log('Loaded: ' + url.split('/').pop());
    return collada.scene;
}

// ============================================================
// PUBLIC: Update arm poses from /joint_states
// All UR5e joints have axis="0 0 1" → rotateZ in local frame.
// The joint-origin rpy (initialRpy) maps local Z → correct world axis.
// ============================================================
export function updateArmPoses(msg) {
    for (let i = 0; i < msg.name.length; i++) {
        const fullName = msg.name[i];
        const angle = msg.position[i];

        let side;
        if (fullName.startsWith('left_')) side = 'left';
        else if (fullName.startsWith('right_')) side = 'right';
        else continue;

        const jointInfos = arms[side];
        if (!jointInfos) continue;

        // Extract joint suffix: "left_shoulder_pan_joint" → "shoulder_pan_joint"
        const jointName = fullName.replace(/^(left_|right_)/, '');
        const entry = jointInfos[jointName];
        if (!entry) continue;

        // Reset to joint-origin rpy, then rotateZ (URDF axis is always Z)
        entry.group.rotation.set(...entry.initialRpy);
        entry.group.rotateZ(angle);
    }
}