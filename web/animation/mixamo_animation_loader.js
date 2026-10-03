import { FBXLoader } from 'three/addons/loaders/FBXLoader.js';

const ASSET_ROOT = '/assets/animations/mixamo';
const LOCOMOTION_FILES = Object.freeze({
  idle: 'idle.fbx',
  walk: 'walk.fbx',
  run: 'run.fbx',
  jump: 'jump.fbx',
  fall: 'fall.fbx',
  land: 'land.fbx',
});

function boneSignature(root) {
  const signature = new Map();
  root.traverse(object => {
    if (!object.isBone) return;
    let parent = object.parent;
    while (parent && !parent.isBone) parent = parent.parent;
    signature.set(object.name, parent?.name || '');
  });
  return signature;
}

function assertSameSkeleton(reference, candidate, file) {
  const expected = boneSignature(reference);
  const actual = boneSignature(candidate);
  if (expected.size !== actual.size) throw new Error(`Mixamo clip ${file} has a different bone count.`);
  for (const [name, parent] of expected) {
    if (actual.get(name) !== parent) throw new Error(`Mixamo clip ${file} has an incompatible skeleton at ${name}.`);
  }
}

function measureRigHeight(root) {
  root.updateMatrixWorld(true);
  let lowest = Infinity;
  let highest = -Infinity;
  root.traverse(object => {
    if (!object.isBone) return;
    const position = object.getWorldPosition(object.position.clone());
    lowest = Math.min(lowest, position.y);
    highest = Math.max(highest, position.y);
  });
  const height = (highest - lowest) * .01;
  if (!Number.isFinite(height) || height < .5) throw new Error('Mixamo source skeleton has invalid height.');
  return height;
}

function measureStrideMeters(clip) {
  const track = clip.tracks.find(item => item.name === 'mixamorigHips.position');
  if (!track || track.values.length < 6) return 0;
  const last = track.values.length - 3;
  return Math.hypot(track.values[last] - track.values[0], track.values[last + 2] - track.values[2]) * .01;
}

export async function loadMixamoAnimationSet(loader = new FBXLoader()) {
  const entries = await Promise.all(Object.entries(LOCOMOTION_FILES).map(async ([state, file]) => {
    const asset = await loader.loadAsync(`${ASSET_ROOT}/${file}`);
    const clip = asset.animations?.[0];
    if (!clip) throw new Error(`Mixamo animation ${file} contains no animation clip.`);
    clip.name = state;
    return { state, file, asset, clip };
  }));

  const sourceRig = entries[0].asset;
  for (const entry of entries.slice(1)) assertSameSkeleton(sourceRig, entry.asset, entry.file);
  const sourceHeightMeters = measureRigHeight(sourceRig);
  const strideMeters = Object.fromEntries(entries.map(({ state, clip }) => [state, measureStrideMeters(clip)]));
  return {
    sourceRig,
    clips: entries.map(entry => entry.clip),
    sourceUnitScale: .01,
    sourceHeightMeters,
    strideMeters,
  };
}
