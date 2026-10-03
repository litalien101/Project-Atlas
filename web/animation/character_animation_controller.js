import * as THREE from 'three';

const STATES = Object.freeze(['idle', 'walk', 'run', 'jump', 'fall', 'land']);
const LOOPING_STATES = new Set(['idle', 'walk', 'run', 'fall']);
const LOCOMOTION_STATES = new Set(['walk', 'run']);
const CROSSFADE_SECONDS = .18;
const LANDING_BLEND_SECONDS = .55;

export class CharacterAnimationController {
  constructor(root, clips, { sourceStrideMeters = {}, targetScale = 1 } = {}) {
    this.mixer = new THREE.AnimationMixer(root);
    const clipsByName = new Map(clips.map(clip => [clip.name, clip]));
    this.actions = new Map();
    for (const state of STATES) {
      const clip = clipsByName.get(state);
      if (!clip?.tracks?.length) throw new Error(`Locomotion set is missing its ${state} clip.`);
      this.actions.set(state, this.mixer.clipAction(clip));
    }

    this.state = null;
    this.targetScale = targetScale;
    this.strideMeters = Object.fromEntries(['walk', 'run'].map(state => [
      state,
      Math.max(.25, (sourceStrideMeters[state] || (state === 'walk' ? 1.8 : 3.0)) * targetScale),
    ]));
    this.landingDuration = Math.min(LANDING_BLEND_SECONDS, this.actions.get('land').getClip().duration);
    this.gaitTimeScale = 1;
    this.targetGaitTimeScale = 1;
    this.setState('idle');
  }

  setState(state, speed = 0) {
    if (!this.actions.has(state)) state = 'idle';
    const action = this.actions.get(state);
    if (state === this.state) {
      this.#setTimeScale(action, state, speed);
      return;
    }

    const previousState = this.state;
    const previousAction = previousState ? this.actions.get(previousState) : null;
    const carryGaitPhase = previousAction && LOCOMOTION_STATES.has(state) && LOCOMOTION_STATES.has(previousState);
    const gaitPhase = carryGaitPhase
      ? (previousAction.time / Math.max(previousAction.getClip().duration, 1e-6)) % 1
      : 0;

    if (previousAction) previousAction.fadeOut(CROSSFADE_SECONDS);
    action.reset();
    if (carryGaitPhase) action.time = gaitPhase * action.getClip().duration;
    action.enabled = true;
    const looping = LOOPING_STATES.has(state);
    action.setLoop(looping ? THREE.LoopRepeat : THREE.LoopOnce, looping ? Infinity : 1);
    action.clampWhenFinished = !looping;
    this.#setTimeScale(action, state, speed);
    action.fadeIn(CROSSFADE_SECONDS).play();
    this.state = state;
  }

  update(delta) {
    const frameDelta = Math.min(delta, .05);
    if (this.state && LOCOMOTION_STATES.has(this.state)) {
      this.gaitTimeScale += (this.targetGaitTimeScale - this.gaitTimeScale) * (1 - Math.exp(-8 * frameDelta));
      this.actions.get(this.state).timeScale = this.gaitTimeScale;
    }
    this.mixer.update(frameDelta);
  }

  #setTimeScale(action, state, speed) {
    if (LOCOMOTION_STATES.has(state)) {
      this.targetGaitTimeScale = Math.max(.25, speed / this.strideMeters[state]);
    } else {
      action.timeScale = 1;
    }
  }
}
