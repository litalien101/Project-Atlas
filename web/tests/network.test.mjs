import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {
  acknowledgeInputs, DeterministicNetworkQueue, FakeClock, FixedStepRunner, NetworkSimulator,
  integrateMovement, integrateVerticalMovement, SnapshotBuffer, walkablePosition,
} from '../network.js';

const movementContract = JSON.parse(readFileSync(fileURLToPath(new URL('../../tests/fixtures/movement-contract.json', import.meta.url)), 'utf8'));
const WORLD_WIDTH = 40;
const WORLD_HEIGHT = 14;
const WORLD_TERRAIN = Array.from({ length: WORLD_HEIGHT }, () => '.'.repeat(WORLD_WIDTH));

test('fake clock delivers queued packets only when their deadline is reached', () => {
  const clock = new FakeClock(), network = new DeterministicNetworkQueue(clock, 7);
  assert.equal(network.send({ id: 1 }, { latency: 100, jitter: 0 }), true);
  assert.deepEqual(network.tick(), []);
  clock.advance(99);
  assert.deepEqual(network.tick(), []);
  clock.advance(1);
  assert.deepEqual(network.tick(), [{ id: 1 }]);
});

test('packet loss is deterministic for a seeded run', () => {
  const run = () => {
    const clock = new FakeClock(), net = new DeterministicNetworkQueue(clock, 91);
    const results = Array.from({ length: 100 }, (_, id) => net.send({ id }, { loss: 0.2 }));
    return { results, dropped: net.dropped };
  };
  assert.deepEqual(run(), run());
  assert.ok(run().dropped > 0);
});

test('network stress profiles eventually deliver the newest sequenced input with retries', () => {
  const profiles = [
    {latency: 0, jitter: 0, loss: 0},
    {latency: 50, jitter: 10, loss: .01},
    {latency: 120, jitter: 30, loss: .03},
    {latency: 250, jitter: 80, loss: .1},
    {latency: 400, jitter: 150, loss: .2},
  ];
  for (let index = 0; index < profiles.length; index++) {
    const clock = new FakeClock(), net = new DeterministicNetworkQueue(clock, 101 + index);
    const profile = profiles[index];
    for (let sequence = 1; sequence <= 100; sequence++) {
      let attempt = 0, accepted = false;
      while (attempt++ < 100 && !accepted) accepted = net.send({sequence}, profile);
      assert.equal(accepted, true, 'retry should eventually place a packet in the network');
    }
    clock.advance(1000);
    const delivered = net.tick();
    const lastAcknowledged = Math.max(...delivered.map(packet => packet.sequence));
    assert.equal(lastAcknowledged, 100, `latest input arrives for profile ${index}`);
  }
});

test('movement request retries simulated loss and receives the eventual acknowledgement', async () => {
  const randomValues = [0, .9, .5, .9, .5];
  let calls = 0;
  const simulator = new NetworkSimulator(
    () => randomValues.shift() ?? .5,
    async () => {},
    async () => { calls++; return {ok: true, json: async () => ({acknowledged_sequence: 9})}; },
  );
  simulator.setProfile('loss');
  const result = await simulator.request('/api/action', {body: JSON.stringify({sequence: 9})}, {retry: true});
  assert.equal(result.payload.acknowledged_sequence, 9);
  assert.equal(calls, 1);
  assert.equal(simulator.stats.sent, 2);
  assert.equal(simulator.stats.dropped, 1);
  assert.equal(simulator.stats.retries, 1);
});

test('acknowledging every input leaves an empty queue', () => {
  assert.deepEqual(acknowledgeInputs([{sequence: 1}, {sequence: 2}], 2), []);
});

test('cumulative acknowledgement retains only inputs newer than the ack', () => {
  assert.deepEqual(acknowledgeInputs([1, 2, 3, 4].map(sequence => ({sequence})), 2), [{sequence: 3}, {sequence: 4}]);
});

test('fixed-step runner bounds catch-up and resets its interpolation accumulator', () => {
  const runner = new FixedStepRunner(1 / 60, 8);
  let steps = 0;
  assert.equal(runner.update(.05, dt => { assert.equal(dt, 1 / 60); steps++; }), 3);
  assert.equal(steps, 3);
  runner.update(.01, () => { steps++; });
  runner.reset();
  assert.equal(runner.alpha(), 0);
});

test('snapshot buffer handles empty, one-sample, duplicate-time and out-of-order updates', () => {
  const buffer = new SnapshotBuffer();
  assert.equal(buffer.at(1), null);
  buffer.add({time: 100, x: 4, z: 2});
  assert.deepEqual(buffer.at(120), {x: 4, z: 2});
  buffer.add({time: 200, x: 10, z: 6});
  buffer.add({time: 150, x: 7, z: 4});
  buffer.add({time: 150, x: 8, z: 5});
  assert.deepEqual(buffer.at(150), {x: 8, z: 5});
});

test('snapshot interpolation stays bounded for deterministic generated positions', () => {
  let seed = 123456789;
  const random = () => ((seed = (1664525 * seed + 1013904223) >>> 0) / 0x100000000);
  for (let i = 0; i < 2000; i++) {
    const x1 = random() * 2000 - 1000, x2 = random() * 2000 - 1000;
    const z1 = random() * 2000 - 1000, z2 = random() * 2000 - 1000;
    const t1 = Math.floor(random() * 10000), t2 = t1 + 1 + Math.floor(random() * 1000);
    const buffer = new SnapshotBuffer();
    buffer.add({time: t1, x: x1, z: z1}); buffer.add({time: t2, x: x2, z: z2});
    const point = buffer.at((t1 + t2) / 2);
    assert.ok(point.x >= Math.min(x1, x2) - 1e-9 && point.x <= Math.max(x1, x2) + 1e-9);
    assert.ok(point.z >= Math.min(z1, z2) - 1e-9 && point.z <= Math.max(z1, z2) + 1e-9);
  }
});

test('exact movement integration agrees across different frame subdivisions', () => {
  let seed = 246813579;
  const random = () => ((seed = (1103515245 * seed + 12345) >>> 0) / 0x100000000);
  for (let sample = 0; sample < 1000; sample++) {
    const position = {x: random() * 20, z: random() * 20};
    const velocity = {x: random() * 8 - 4, z: random() * 8 - 4};
    const input = {x: random() * 2 - 1, z: random() * 2 - 1};
    const magnitude = Math.hypot(input.x, input.z) || 1;
    input.x /= magnitude; input.z /= magnitude;
    const duration = 0.001 + random() * 0.3, speed = 2.5 + random() * 1.7;
    const whole = integrateMovement(position, velocity, input, duration, speed);
    let split = {position: {...position}, velocity: {...velocity}};
    const slices = 1 + Math.floor(random() * 20), step = duration / slices;
    for (let j = 0; j < slices; j++) split = integrateMovement(split.position, split.velocity, input, step, speed);
    assert.ok(Math.hypot(whole.position.x - split.position.x, whole.position.z - split.position.z) < 1e-8);
    assert.ok(Math.hypot(whole.velocity.x - split.velocity.x, whole.velocity.z - split.velocity.z) < 1e-8);
  }
});

test('browser movement follows the shared client/server fixed-tick contract', () => {
  let position = {...movementContract.start}, velocity = {x: 0, z: 0};
  for (const segment of movementContract.segments) {
    for (let tick = 0; tick < segment.ticks; tick++) {
      const result = integrateMovement(position, velocity, segment.input,
        1 / movementContract.fixed_hz, segment.run ? 4.2 : 2.5);
      position = result.position;
      velocity = result.velocity;
    }
  }
  assert.ok(Math.hypot(position.x - movementContract.expected.position.x,
    position.z - movementContract.expected.position.z) < 1e-9);
  assert.ok(Math.hypot(velocity.x - movementContract.expected.velocity.x,
    velocity.z - movementContract.expected.velocity.z) < 1e-9);
});

test('browser jump trajectory follows the shared server movement contract', () => {
  const jump = movementContract.jump;
  let motion = {height: 0, velocity: 0, grounded: true, jumpBuffer: 0, coyoteTime: jump.coyote_seconds};
  let peak = 0, apexTick = null, landingTick = null;
  for (let tick = 1; tick <= 60; tick++) {
    motion = integrateVerticalMovement(motion, tick === 1, 1 / movementContract.fixed_hz);
    if (motion.height > peak) { peak = motion.height; apexTick = tick; }
    if (tick > 1 && motion.grounded && landingTick === null) landingTick = tick;
  }
  assert.equal(apexTick, jump.expected_apex_tick);
  assert.ok(Math.abs(peak - jump.expected_apex_height) < 1e-12);
  assert.equal(landingTick, jump.expected_landing_tick);
  assert.equal(motion.height, 0);
  assert.equal(motion.velocity, 0);
  assert.equal(motion.grounded, true);
});

test('browser terrain footprint matches the shared collision contract', () => {
  for (const sample of movementContract.walkability) {
    assert.equal(walkablePosition(sample.x, sample.z, WORLD_TERRAIN, WORLD_WIDTH, WORLD_HEIGHT), sample.walkable);
  }
});

test('browser circular colliders reject solid props and leave clearance around them', () => {
  for (const sample of movementContract.obstacleCollisions) {
    assert.equal(walkablePosition(sample.x, sample.z, WORLD_TERRAIN, WORLD_WIDTH, WORLD_HEIGHT, .2, [sample.obstacle]), sample.walkable);
  }
});
