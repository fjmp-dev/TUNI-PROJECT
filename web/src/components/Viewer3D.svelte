<script>
  // Placeholder. The real Three.js viewer (loads the UR5e .dae meshes, builds the
  // kinematic chain and animates both arms from /joint_states) lands in the next
  // increment. Per the project constraint, it will show joints AS REPORTED and
  // will NOT compensate for the reversed physical mounting.
</script>

<div class="panel">
  <div class="panel-header">
    <h2>Visor 3D</h2>
    <span class="badge">próximamente</span>
  </div>
  <div class="panel-body">
    <div class="stub">
      Visor 3D de los brazos UR5e — en construcción.<br />
      Mostrará los joints en vivo desde <span class="mono">/joint_states</span>, sin corregir el
      montaje invertido.
    </div>
  </div>
</div>

<style>
  .stub {
    aspect-ratio: 16 / 10;
    background: var(--panel-2);
    border-radius: 6px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    color: var(--muted);
    font-size: 13px;
    line-height: 1.6;
    padding: 16px;
  }
</style>
