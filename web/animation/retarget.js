import * as THREE from 'three';

const _sourceRestInverse = new THREE.Quaternion();
const _sourceKey = new THREE.Quaternion();
const _targetRest = new THREE.Quaternion();

function canonicalBoneName(name) { return name.toLowerCase().replace(/[^a-z0-9]/g, ''); }

/**
 * Transfer local animation deltas onto the target rig's authored rest pose.
 * Root position tracks are intentionally omitted: world movement and jumping
 * are owned by Atlas, so clips cannot pull the visible model off its anchor.
 */
export function retargetAnimationClips(targetRoot, sourceRig, clips) {
  sourceRig.updateMatrixWorld(true);
  targetRoot.updateMatrixWorld(true);
  const targets = new Map();
  targetRoot.traverse(object => {
    if (object.isBone) targets.set(canonicalBoneName(object.name), object);
  });

  const sourceBones = new Map();
  sourceRig.traverse(object => {
    if (object.isBone) sourceBones.set(object.name, object);
  });

  return clips.map(clip => {
    const outputTracks = [];
    for (const track of clip.tracks) {
      const match = track.name.match(/^(.+)\.(quaternion|position|scale)$/i);
      if (!match || match[2] !== 'quaternion') continue;
      const [, sourceName] = match;
      // Blender's glTF export inserts an axis correction on the root hips
      // joint. Applying the FBX hips delta here rotates that correction twice
      // and makes the avatar sway/roll, so Atlas owns the root orientation.
      if (canonicalBoneName(sourceName) === 'mixamorighips') continue;
      const sourceBone = sourceBones.get(sourceName);
      const targetBone = targets.get(canonicalBoneName(sourceName));
      if (!sourceBone || !targetBone) continue;

      _sourceRestInverse.copy(sourceBone.quaternion).invert();
      _targetRest.copy(targetBone.quaternion);
      const values = new Float32Array(track.values.length);
      for (let i = 0; i < track.values.length; i += 4) {
        _sourceKey.fromArray(track.values, i);
        _sourceKey.premultiply(_sourceRestInverse);
        _sourceKey.premultiply(_targetRest).normalize();
        _sourceKey.toArray(values, i);
      }
      outputTracks.push(new THREE.QuaternionKeyframeTrack(
        `${targetBone.uuid}.quaternion`, track.times.slice(), values,
      ));
    }
    if (!outputTracks.length) throw new Error(`Animation ${clip.name} has no compatible Atlas bone tracks.`);
    return new THREE.AnimationClip(clip.name, clip.duration, outputTracks, clip.blendMode);
  });
}
