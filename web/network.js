export const NETWORK_PROFILES = Object.freeze({
  local: { latency: 0, jitter: 0, loss: 0 },
  good: { latency: 50, jitter: 10, loss: 0.01 },
  average: { latency: 120, jitter: 30, loss: 0.03 },
  bad: { latency: 250, jitter: 80, loss: 0.10 },
  loss: { latency: 80, jitter: 15, loss: 0.10 },
});

export class NetworkSimulator {
  constructor(random = Math.random, wait = ms => new Promise(resolve => setTimeout(resolve, ms)), transport = (...args) => fetch(...args)) {
    this.random = random;
    this.wait = wait;
    this.transport = transport;
    this.profileName = 'local';
    this.profile = NETWORK_PROFILES.local;
    this.enabled = false;
    this.stats = { sent: 0, received: 0, dropped: 0, retries: 0, ping: 0, jitter: 0 };
    this.previousPing = null;
  }

  setProfile(name) {
    if (!Object.hasOwn(NETWORK_PROFILES, name)) throw new Error(`Unknown network profile: ${name}`);
    this.profileName = name;
    this.profile = NETWORK_PROFILES[name];
    this.enabled = name !== 'local';
  }

  async request(url, options, { retry = false } = {}) {
    const attempts = retry ? 4 : 1;
    let lastError;
    for (let attempt = 0; attempt < attempts; attempt++) {
      this.stats.sent++;
      const started = performance.now();
      try {
        await this.#transmitDelay();
        const response = await this.transport(url, options);
        const payload = await response.json();
        await this.#transmitDelay();
        const ping = performance.now() - started;
        this.stats.jitter = this.previousPing === null ? 0 : this.stats.jitter * 0.8 + Math.abs(ping - this.previousPing) * 0.2;
        this.previousPing = ping;
        this.stats.ping = this.stats.ping ? this.stats.ping * 0.8 + ping * 0.2 : ping;
        this.stats.received++;
        return { response, payload };
      } catch (error) {
        lastError = error;
        if (attempt + 1 >= attempts) break;
        this.stats.retries++;
        await this.wait(Math.min(100 * (2 ** attempt), 400));
      }
    }
    throw lastError;
  }

  async #transmitDelay() {
    if (!this.enabled) return;
    if (this.random() < this.profile.loss) {
      this.stats.dropped++;
      throw new Error('Simulated packet loss');
    }
    const oneWayMs = this.profile.latency / 2 + (this.random() * 2 - 1) * this.profile.jitter / 2;
    if (oneWayMs > 0) await this.wait(oneWayMs);
  }

  get lossRate() {
    return this.stats.sent ? this.stats.dropped / this.stats.sent : 0;
  }
}

export function acknowledgeInputs(pending, acknowledgedSequence) {
  return pending.filter(input => input.sequence > acknowledgedSequence);
}

export function integrateMovement(position, velocity, input, dt, speed, acceleration = 11) {
  const targetX = input.x * speed, targetZ = input.z * speed;
  const braking = Math.hypot(targetX, targetZ) < 1e-6;
  const rate = braking ? 28 : acceleration;
  const decay = Math.exp(-rate * dt);
  let nextVelocityX = targetX + (velocity.x - targetX) * decay;
  let nextVelocityZ = targetZ + (velocity.z - targetZ) * decay;
  if (braking && Math.hypot(nextVelocityX, nextVelocityZ) < 0.035) {
    nextVelocityX = 0;
    nextVelocityZ = 0;
  }
  return {
    position: {
      x: position.x + targetX * dt + (velocity.x - targetX) * (1 - decay) / rate,
      z: position.z + targetZ * dt + (velocity.z - targetZ) * (1 - decay) / rate,
    },
    velocity: {
      x: nextVelocityX,
      z: nextVelocityZ,
    },
  };
}

export function integrateVerticalMovement(motion, jumpPressed, dt, surfaceHeight = 0) {
  let { height = 0, velocity = 0, grounded = true, jumpBuffer = 0, coyoteTime = 0.1 } = motion;
  let remaining = dt;
  if (jumpPressed) jumpBuffer = 0.12;
  while (remaining > 1e-9) {
    const step = Math.min(remaining, 1 / 60);
    if (grounded) coyoteTime = 0.1;
    else coyoteTime = Math.max(0, coyoteTime - step);
    if (jumpBuffer > 0 && (grounded || coyoteTime > 0)) {
      velocity = 5.2;
      grounded = false;
      jumpBuffer = 0;
      coyoteTime = 0;
    }
    jumpBuffer = Math.max(0, jumpBuffer - step);
    if (!grounded) {
      velocity -= 16 * step;
      height += velocity * step;
      if (height <= surfaceHeight) {
        height = surfaceHeight; velocity = 0; grounded = true; coyoteTime = 0.1;
      }
    } else height = surfaceHeight;
    remaining -= step;
  }
  return { height, velocity, grounded, jumpBuffer, coyoteTime };
}

export const MAX_STEP_UP = 0.28;
export const LEDGE_DROP = 0.55;
export const MAX_WALKABLE_GRADE = 0.65;

export function sampleGroundHeight(x, z, features = []) {
  let height = 0;
  const slope = features.find(feature => feature.kind === 'slope');
  if (slope && z >= slope.z_min && z <= slope.z_max) {
    const progress = Math.max(0, Math.min(1, (x - slope.x_min) / (slope.x_max - slope.x_min)));
    height = Math.max(height, slope.height * progress);
  }
  const ledge = features.find(feature => feature.kind === 'ledge');
  if (ledge && x >= ledge.x_min && x <= ledge.x_max && z >= ledge.z_min && z <= ledge.z_max) {
    height = Math.max(height, ledge.height);
  }
  if (ledge && x >= ledge.ramp_x_min && x <= ledge.ramp_x_max && z > ledge.z_max && z <= ledge.ramp_z_max) {
    height = Math.max(height, ledge.height * (ledge.ramp_z_max - z) / (ledge.ramp_z_max - ledge.z_max));
  }
  return height;
}

// Keep footprint sampling identical to atlas_server.world.walkable_position.
// The server remains authoritative; this copy is only for immediate prediction.
export function walkablePosition(x, z, terrain, width, height, radius = 0.2, obstacles = []) {
  const offsets = [
    [-radius, 0], [radius, 0], [0, -radius], [0, radius],
    [-radius * 0.7, -radius * 0.7], [radius * 0.7, -radius * 0.7],
    [-radius * 0.7, radius * 0.7], [radius * 0.7, radius * 0.7],
  ];
  if (!offsets.every(([ox, oz]) => {
    const px = x + ox, pz = z + oz;
    const cellX = px < 0 ? Math.floor(px) : Math.floor(px + 0.5);
    const cellZ = pz < 0 ? Math.floor(pz) : Math.floor(pz + 0.5);
    return cellX >= 0 && cellX < width && cellZ >= 0 && cellZ < height && terrain[cellZ][cellX] !== '~';
  })) return false;
  return obstacles.every(obstacle => {
    if (obstacle.shape === 'box') {
      return Math.abs(x - obstacle.x) >= radius + obstacle.half_width ||
        Math.abs(z - obstacle.z) >= radius + obstacle.half_depth;
    }
    return Math.hypot(x - obstacle.x, z - obstacle.z) >= radius + obstacle.radius;
  });
}

export class FixedStepRunner {
  constructor(fixedDelta = 1 / 60, maxSteps = 8) {
    if (!Number.isFinite(fixedDelta) || fixedDelta <= 0 || !Number.isInteger(maxSteps) || maxSteps < 1) {
      throw new RangeError('Fixed-step configuration is invalid.');
    }
    this.fixedDelta = fixedDelta;
    this.maxSteps = maxSteps;
    this.accumulator = 0;
  }
  update(frameDelta, tick) {
    if (!Number.isFinite(frameDelta) || frameDelta < 0) throw new RangeError('Frame delta must be finite and nonnegative.');
    this.accumulator += Math.min(frameDelta, this.fixedDelta * this.maxSteps);
    let steps = 0;
    while (this.accumulator + 1e-12 >= this.fixedDelta && steps < this.maxSteps) {
      tick(this.fixedDelta);
      this.accumulator -= this.fixedDelta;
      steps++;
    }
    return steps;
  }
  alpha() { return Math.min(1, this.accumulator / this.fixedDelta); }
  reset() { this.accumulator = 0; }
}

export class FakeClock {
  constructor() { this.time = 0; }
  now() { return this.time; }
  advance(ms) { if (!Number.isFinite(ms) || ms < 0) throw new RangeError('Clock advance must be finite and nonnegative.'); this.time += ms; }
}

export class DeterministicNetworkQueue {
  constructor(clock, seed = 1) { this.clock = clock; this.seed = seed >>> 0; this.queue = []; this.dropped = 0; }
  random() { this.seed = (1664525 * this.seed + 1013904223) >>> 0; return this.seed / 0x100000000; }
  send(packet, { latency = 0, jitter = 0, loss = 0 } = {}) {
    if (this.random() < loss) { this.dropped++; return false; }
    const delay = Math.max(0, latency + (this.random() * 2 - 1) * jitter);
    this.queue.push({ packet, deliveryTime: this.clock.now() + delay, order: this.seed });
    this.queue.sort((a, b) => a.deliveryTime - b.deliveryTime || a.order - b.order);
    return true;
  }
  tick() {
    const now = this.clock.now(), ready = [];
    while (this.queue.length && this.queue[0].deliveryTime <= now) ready.push(this.queue.shift().packet);
    return ready;
  }
}

export class SnapshotBuffer {
  constructor(limit = 50) { this.limit = limit; this.items = []; }
  add(snapshot) {
    const index = this.items.findIndex(item => item.time >= snapshot.time);
    if (index < 0) this.items.push(snapshot);
    else if (this.items[index].time === snapshot.time) this.items[index] = snapshot;
    else this.items.splice(index, 0, snapshot);
    if (this.items.length > this.limit) this.items.splice(0, this.items.length - this.limit);
  }
  at(time) {
    if (!this.items.length) return null;
    if (this.items.length === 1 || time <= this.items[0].time) return this.#pose(this.items[0]);
    for (let i = 0; i < this.items.length - 1; i++) {
      const older = this.items[i], newer = this.items[i + 1];
      if (older.time <= time && time <= newer.time) {
        const span = newer.time - older.time;
        const alpha = span ? (time - older.time) / span : 0;
        const pose = { x: older.x + (newer.x - older.x) * alpha, z: older.z + (newer.z - older.z) * alpha };
        for (const field of ['height', 'vx', 'vz', 'vertical_velocity']) {
          if (Number.isFinite(older[field]) && Number.isFinite(newer[field])) {
            pose[field] = older[field] + (newer[field] - older[field]) * alpha;
          }
        }
        if (older.grounded !== undefined || newer.grounded !== undefined) {
          pose.grounded = alpha < 1 ? older.grounded : newer.grounded;
        }
        return pose;
      }
    }
    // A short, speed-limited extrapolation hides small delivery gaps. Holding the
    // last sample after that avoids predicting through walls during longer stalls.
    const latest = this.items.at(-1);
    if (this.items.length < 2 || time <= latest.time) return this.#pose(latest);
    const previous = this.items.at(-2);
    const span = latest.time - previous.time;
    if (span <= 0) return this.#pose(latest);
    const elapsed = Math.min(time - latest.time, 100);
    let vx = Number.isFinite(latest.vx) ? latest.vx * elapsed / 1000 : (latest.x - previous.x) * elapsed / span;
    let vz = Number.isFinite(latest.vz) ? latest.vz * elapsed / 1000 : (latest.z - previous.z) * elapsed / span;
    const distance = Math.hypot(vx, vz);
    const maximumDistance = 4.5 * elapsed / 1000;
    if (distance > maximumDistance && distance > 0) {
      vx *= maximumDistance / distance;
      vz *= maximumDistance / distance;
    }
    const pose = {...this.#pose(latest), x: latest.x + vx, z: latest.z + vz};
    if (Number.isFinite(latest.height) && Number.isFinite(latest.vertical_velocity)) {
      pose.height = Math.max(0, latest.height + latest.vertical_velocity * elapsed / 1000);
    }
    return pose;
  }
  #pose(snapshot) {
    const pose = {x: snapshot.x, z: snapshot.z};
    for (const field of ['height', 'vx', 'vz', 'vertical_velocity', 'grounded']) {
      if (snapshot[field] !== undefined) pose[field] = snapshot[field];
    }
    return pose;
  }
}
