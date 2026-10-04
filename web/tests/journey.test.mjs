import assert from 'node:assert/strict';
import test from 'node:test';
import { getJourneyHudState } from '../journey.js';

const state = overrides => ({
  player: { x: 3, y: 10 },
  inventory: { lumen_reed: 0 },
  rules: { beacon_lumen_reed_cost: 3 },
  mara: { x: 7, y: 7 },
  beacon: { x: 15, y: 4 },
  reed_patches: [{ id: 'near', x: 4, y: 9 }, { id: 'far', x: 9, y: 8 }],
  mara_met: false,
  beacon_awake: false,
  ...overrides,
});

test('journey guides a new traveler to Mara with live range', () => {
  const journey = getJourneyHudState(state());
  assert.equal(journey.objective, 'Find Mara along the western path');
  assert.equal(journey.targetLabel, 'MARA');
  assert.equal(journey.distanceText, '5.0 away');
  assert.equal(journey.currentStep, 0);
  assert.equal(journey.completedMilestones, 0);
});

test('journey switches to the nearest reed patch and reports remaining offering', () => {
  const journey = getJourneyHudState(state({ mara_met: true, inventory: { lumen_reed: 1 } }));
  assert.equal(journey.objective, 'Gather Lumen reeds');
  assert.equal(journey.hint, 'Gather 2 more Lumen reeds from the quiet patches.');
  assert.equal(journey.targetLabel, 'LUMEN REED');
  assert.equal(journey.distanceText, '1.4 away');
  assert.equal(journey.reedCountText, '1 / 3');
  assert.equal(journey.completedMilestones, 1);
});

test('journey points to the Beacon once the offering is ready', () => {
  const journey = getJourneyHudState(state({ mara_met: true, inventory: { lumen_reed: 3 } }));
  assert.equal(journey.objective, 'Wake the Listening Beacon');
  assert.equal(journey.targetLabel, 'LISTENING BEACON');
  assert.equal(journey.distanceText, '13.4 away');
  assert.equal(journey.completedMilestones, 2);
});

test('journey marks every milestone complete after the Beacon awakens', () => {
  const journey = getJourneyHudState(state({ mara_met: true, inventory: { lumen_reed: 3 }, beacon_awake: true }));
  assert.equal(journey.objective, 'A signal answers beyond the valley');
  assert.equal(journey.targetLabel, 'SIGNAL CARRIED');
  assert.equal(journey.distanceText, 'Beyond the valley');
  assert.equal(journey.completedMilestones, 3);
  assert.equal(journey.progressPercent, 100);
});

test('journey reports a missing patch instead of inventing a route', () => {
  const journey = getJourneyHudState(state({ mara_met: true, inventory: { lumen_reed: 0 }, reed_patches: [] }));
  assert.equal(journey.distanceText, 'No patches remain');
});
