import assert from 'node:assert/strict';
import test from 'node:test';
import { Group } from 'three';
import { ModelAssetLoader, modelAssetUrl } from '../model_loader.js';

test('modelAssetUrl encodes nested same-origin asset paths', () => {
  assert.equal(
    modelAssetUrl('base character/Universal [Standard]/hero.gltf'),
    '/assets/base%20character/Universal%20%5BStandard%5D/hero.gltf',
  );
});

test('modelAssetUrl rejects traversal, absolute, and unsupported paths', () => {
  for (const path of [
    '',
    '/models/hero.glb',
    '../hero.glb',
    'models/../hero.glb',
    'models\\hero.glb',
    'models/hero.fbx',
    'https://example.test/hero.glb',
  ]) {
    assert.throws(() => modelAssetUrl(path), TypeError, path);
  }
});

test('ModelAssetLoader deduplicates concurrent fetches and clones each scene', async () => {
  const sourceScene = new Group();
  sourceScene.name = 'rigged-source';
  const gltf = { scene: sourceScene, scenes: [sourceScene], animations: [{ name: 'idle' }] };
  let loadCount = 0;
  const loader = new ModelAssetLoader({
    loader: { loadAsync: async () => { loadCount++; return gltf; } },
  });

  const [first, second] = await Promise.all([
    loader.load('characters/hero.glb'),
    loader.load('characters/hero.glb'),
  ]);

  assert.equal(loadCount, 1);
  assert.notEqual(first.scene, second.scene);
  assert.notEqual(first.scene, sourceScene);
  assert.equal(first.scene.name, sourceScene.name);
  assert.equal(first.scenes[0], first.scene);
  assert.equal(first.animations, gltf.animations);
});

test('ModelAssetLoader retries transient server failures but propagates permanent errors', async () => {
  const sourceScene = new Group();
  let attempts = 0;
  const loader = new ModelAssetLoader({
    loader: { loadAsync: async () => {
      attempts++;
      if (attempts === 1) throw new Error('THREE.GLTFLoader: Failed to load buffer "Wall_Plaster_Straight.bin".');
      return { scene: sourceScene, scenes: [sourceScene], animations: [] };
    } },
  });

  const gltf = await loader.load('characters/retry.glb');
  assert.equal(attempts, 2);
  assert.notEqual(gltf.scene, sourceScene);

  const permanent = new ModelAssetLoader({
    loader: { loadAsync: async () => { throw new Error('HTTP 404 Not Found'); } },
  });
  await assert.rejects(permanent.load('characters/missing.glb'), /404/);
});
