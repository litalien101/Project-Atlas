import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import { ThirdPersonCamera } from '../camera/third_person_camera.js';

test('third-person camera shortens its boom for world obstacles and restores the preferred distance', () => {
  const controller = new ThirdPersonCamera(new THREE.PerspectiveCamera());
  controller.focus.set(0, 1.15, 0);
  controller.placeCamera(5.4);

  const blockedDistance = controller.resolveObstructionDistance([
    { kind: 'npc', x: 0, z: 2, radius: .5 },
  ]);
  const clearDistance = controller.resolveObstructionDistance([]);

  assert.ok(blockedDistance < clearDistance);
  assert.ok(blockedDistance > .65);
  assert.ok(Math.abs(clearDistance - 5.4) < 1e-12);
});

test('camera boom placement uses the requested distance on every axis', () => {
  const controller = new ThirdPersonCamera(new THREE.PerspectiveCamera());
  controller.focus.set(1, 2, 3);
  controller.pitch = .2;
  controller.placeCamera(2);

  assert.ok(Math.abs(controller.desired.y - (2 + Math.sin(.2) * 2)) < 1e-12);
});
