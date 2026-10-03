import * as THREE from 'three';

const DEFAULTS = Object.freeze({ sensitivity: 1, zoomSpeed: 1, smoothing: 8, invertY: false });

export class ThirdPersonCamera {
  constructor(camera) {
    this.camera = camera;
    this.yaw = 0;
    this.pitch = 0.2;
    this.distance = 5.4;
    this.currentDistance = 5.4;
    this.targetDistance = 5.4;
    this.focus = new THREE.Vector3();
    this.targetFocus = new THREE.Vector3();
    this.initialized = false;
    this.settings = this.loadSettings();
    this.desired = new THREE.Vector3();
  }

  loadSettings() {
    try {
      const saved = JSON.parse(localStorage.getItem('atlas.camera.settings') || '{}');
      return { ...DEFAULTS, ...saved };
    } catch { return { ...DEFAULTS }; }
  }

  setOption(name, value) {
    if (!(name in DEFAULTS)) return;
    this.settings[name] = name === 'invertY' ? Boolean(value) : Number(value);
    try { localStorage.setItem('atlas.camera.settings', JSON.stringify(this.settings)); } catch { /* storage may be disabled */ }
  }

  snap(position) {
    this.focus.set(position.x, position.y + 1.15, position.z);
    this.distance = this.targetDistance;
    this.currentDistance = this.distance;
    this.placeCamera(this.currentDistance);
    this.camera.lookAt(this.focus);
    this.initialized = true;
  }

  zoom(wheelDelta) {
    this.targetDistance = THREE.MathUtils.clamp(this.targetDistance + wheelDelta * 0.004 * this.settings.zoomSpeed, 2.5, 14);
  }

  update(delta, position, intent, obstacles = []) {
    if (!this.initialized) this.snap(position);
    const smoothing = Math.max(1, this.settings.smoothing);
    const alpha = 1 - Math.exp(-smoothing * delta);
    this.yaw -= intent.mouseX * 0.005 * this.settings.sensitivity;
    // Positive orbit yaw moves the camera right but turns the view left;
    // reverse the arrow-key mapping so left/right match the view direction.
    this.yaw -= intent.yaw * 1.9 * delta;
    const invert = this.settings.invertY ? -1 : 1;
    this.pitch = THREE.MathUtils.clamp(
      this.pitch + intent.mouseY * 0.004 * this.settings.sensitivity * invert + intent.pitch * 1.25 * delta,
      -0.45, 1.05,
    );
    this.distance += (this.targetDistance - this.distance) * alpha;
    this.targetFocus.set(position.x, position.y + 1.15, position.z);
    this.focus.lerp(this.targetFocus, alpha);
    this.placeCamera(this.distance);
    const safeDistance = this.resolveObstructionDistance(obstacles);
    if (safeDistance < this.distance - .01) {
      this.currentDistance = safeDistance;
      this.placeCamera(this.currentDistance);
      this.camera.position.copy(this.desired);
    }else{
      this.currentDistance += (this.distance - this.currentDistance) * (1 - Math.exp(-5 * delta));
      this.placeCamera(this.currentDistance);
      this.camera.position.lerp(this.desired,alpha);
    }
    this.camera.lookAt(this.focus);
  }

  resolveObstructionDistance(obstacles) {
    const dx = this.desired.x - this.focus.x;
    const dy = this.desired.y - this.focus.y;
    const dz = this.desired.z - this.focus.z;
    const length = Math.hypot(dx, dy, dz) || 1;
    const ux = dx / length, uy = dy / length, uz = dz / length;
    let safeDistance = length;
    for (const obstacle of obstacles || []) {
      const scale = obstacle.scale || 1;
      const radius = obstacle.kind === 'tree' ? Math.max(.48, .68 * scale) : (obstacle.radius || .3) + .28;
      const centerY = obstacle.kind === 'tree' ? .92 * scale : obstacle.kind === 'beacon' ? 1.35 : .82;
      const ox = obstacle.x - this.focus.x, oy = centerY - this.focus.y;
      const oz = (obstacle.z ?? obstacle.y) - this.focus.z;
      const along = ox * ux + oy * uy + oz * uz;
      if (along <= .12 || along >= safeDistance) continue;
      const perpendicularSquared = ox * ox + oy * oy + oz * oz - along * along;
      const radiusSquared = (radius + .18) * (radius + .18);
      if (perpendicularSquared >= radiusSquared) continue;
      const hit = along - Math.sqrt(radiusSquared - perpendicularSquared) - .16;
      safeDistance = Math.min(safeDistance, Math.max(.65, hit));
    }
    return safeDistance;
  }

  placeCamera(distance = this.distance) {
    const horizontal = Math.cos(this.pitch) * distance;
    this.desired.set(
      this.focus.x + Math.sin(this.yaw) * horizontal,
      this.focus.y + Math.sin(this.pitch) * distance,
      this.focus.z + Math.cos(this.yaw) * horizontal,
    );
  }
}
