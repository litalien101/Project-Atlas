import * as THREE from 'three';
import { FixedStepRunner, NetworkSimulator, acknowledgeInputs, integrateMovement, integrateVerticalMovement, sampleGroundHeight, MAX_STEP_UP, MAX_WALKABLE_GRADE, LEDGE_DROP, walkablePosition } from './network.js';
import { InputManager } from './input/input_manager.js';
import { ThirdPersonCamera } from './camera/third_person_camera.js';
import { CharacterAnimationController } from './animation/character_animation_controller.js';
import { loadMixamoAnimationSet } from './animation/mixamo_animation_loader.js';
import { retargetAnimationClips } from './animation/retarget.js';
import { ModelAssetLoader } from './model_loader.js';

const modelAssetLoader = new ModelAssetLoader();
// No licensed Atlas runtime character is currently registered. Keep the
// loading hook ready for the reviewed replacement model without fetching the
// removed, rights-unverified prototype.
const travelerModelPaths = Object.freeze({});
let travelerAnimationsPromise = null;
const travelerModelBounds = new Map();
function loadTravelerAnimations() {
  if (!travelerAnimationsPromise) {
    travelerAnimationsPromise = loadMixamoAnimationSet().catch(error => {
      console.warn('Traveler animations unavailable; keeping the uploaded character in its rest pose.', error);
      return null;
    });
  }
  return travelerAnimationsPromise;
}

const canvas = document.querySelector('#world');
const $ = (selector) => document.querySelector(selector);
const scene = new THREE.Scene();
function makeSkyTexture() {
  const sky = document.createElement('canvas');
  sky.width = 2;
  sky.height = 512;
  const context = sky.getContext('2d');
  const gradient = context.createLinearGradient(0, 0, 0, sky.height);
  gradient.addColorStop(0, '#91a8ac');
  gradient.addColorStop(.48, '#c2c7b8');
  gradient.addColorStop(.78, '#e2c99e');
  gradient.addColorStop(1, '#d5bd91');
  context.fillStyle = gradient;
  context.fillRect(0, 0, sky.width, sky.height);
  const texture = new THREE.CanvasTexture(sky);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}
scene.background = makeSkyTexture();
scene.fog = new THREE.Fog('#c5c4ad', 25, 66);

const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.75));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFShadowMap;
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.08;

const camera = new THREE.PerspectiveCamera(56, 1, 0.1, 140);
camera.zoom = 1;
camera.updateProjectionMatrix();

scene.add(new THREE.HemisphereLight('#e4e9d4', '#34483a', 1.55));
const sun = new THREE.DirectionalLight('#ffe0ad', 2.65);
sun.position.set(-12, 16, 10);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
sun.shadow.camera.left = -22; sun.shadow.camera.right = 22;
sun.shadow.camera.top = 22; sun.shadow.camera.bottom = -22;
sun.shadow.normalBias = 0.035;
scene.add(sun);

const world = new THREE.Group();
scene.add(world);
const player = makeCharacter('player');
const inputManager = new InputManager(canvas);
const cameraController = new ThirdPersonCamera(camera);
inputManager.setZoomHandler(delta => cameraController.zoom(delta));
world.add(player);

let game = null;
let worldSurfaceFeatures = [];
let busy = false;
let toastTimer = 0;
let clickPointer = null;
let positionCorrection = { x: 0, z: 0 };
let predictedVelocity = { x: 0, z: 0 };
let verticalMotion = { height: 0, velocity: 0, grounded: true, jumpBuffer: 0, coyoteTime: .1 };
let verticalCorrection = 0;
let sessionToken = sessionStorage.getItem('atlas.local.session') || '';
let sessionRecovery = null;
const network = new NetworkSimulator(undefined, undefined, authenticatedFetch);
const movementClock = new FixedStepRunner(1 / 60, 8);
const predictedPosition = { x: 0, z: 0 };
const previousPredictedPosition = { x: 0, z: 0 };
let movementSequence = 0;
let acknowledgedSequence = 0;
let pendingInputs = [];
let outgoingInputs = [];
let correctionDistance = 0;
let maxCorrectionDistance = 0;
let largeCorrections = 0;
let lastNetworkHudAt = 0;
let initialStateLoaded = false;
let clickDestination = null;
let lastSentInput = { x: 0, z: 0, run: false };
let nextInputAt = 0;
let nextSnapshotPollAt = 0;
let snapshotPollPending = false;
let landingImpact = 0;
let landingTime = 0;
let lastFrameTime = 0;
let targetPlayerYaw = 0;
let audioContext = null;
let ambientBus = null;
let ambientEnabled = true;
let birdCallTimer = null;
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
let terrainMesh = null;

function material(color, roughness = 0.86, extra = {}) {
  return new THREE.MeshStandardMaterial({ color, roughness, ...extra });
}

function addMesh(parent, geometry, mat, position, options = {}) {
  const mesh = new THREE.Mesh(geometry, mat);
  mesh.position.set(...position);
  mesh.castShadow = options.castShadow ?? true;
  mesh.receiveShadow = options.receiveShadow ?? true;
  if (options.rotation) mesh.rotation.set(...options.rotation);
  parent.add(mesh);
  return mesh;
}

function buildLandscape(state) {
  worldSurfaceFeatures = [];
  buildGround(state);
}

function buildGround(state) {
  const textureCanvas = document.createElement('canvas');
  textureCanvas.width = 1024;
  textureCanvas.height = 512;
  const context = textureCanvas.getContext('2d');
  context.fillStyle = '#65725f';
  context.fillRect(0, 0, textureCanvas.width, textureCanvas.height);

  let seed = 1847;
  const random = () => {
    seed = (seed * 1664525 + 1013904223) >>> 0;
    return seed / 4294967296;
  };
  for (let index = 0; index < 360; index += 1) {
    const x = random() * textureCanvas.width;
    const y = random() * textureCanvas.height;
    const radius = 10 + random() * 62;
    const shade = random() > .52 ? '105, 116, 88' : '43, 66, 54';
    const opacity = .04 + random() * .08;
    for (const offsetX of [-textureCanvas.width, 0, textureCanvas.width]) {
      for (const offsetY of [-textureCanvas.height, 0, textureCanvas.height]) {
        const patchX = x + offsetX;
        const patchY = y + offsetY;
        const patch = context.createRadialGradient(patchX, patchY, 0, patchX, patchY, radius);
        patch.addColorStop(0, `rgba(${shade}, ${opacity})`);
        patch.addColorStop(1, `rgba(${shade}, 0)`);
        context.fillStyle = patch;
        context.fillRect(patchX - radius, patchY - radius, radius * 2, radius * 2);
      }
    }
  }
  for (let index = 0; index < 15000; index += 1) {
    const shade = random() > .5 ? '235, 222, 177' : '21, 39, 31';
    context.fillStyle = `rgba(${shade}, ${.015 + random() * .025})`;
    context.fillRect(2 + random() * (textureCanvas.width - 4), 2 + random() * (textureCanvas.height - 4), 1, 1);
  }
  const groundTexture = new THREE.CanvasTexture(textureCanvas);
  groundTexture.colorSpace = THREE.SRGBColorSpace;
  groundTexture.wrapS = THREE.RepeatWrapping;
  groundTexture.wrapT = THREE.RepeatWrapping;
  groundTexture.anisotropy = renderer.capabilities.getMaxAnisotropy();
  const extentTiles = size => {
    const count = Math.ceil(240 / size);
    return count % 2 === 0 ? count + 1 : count;
  };
  const tilesAcross = extentTiles(state.width);
  const tilesDeep = extentTiles(state.height);
  groundTexture.repeat.set(tilesAcross, tilesDeep);
  const ground = new THREE.Mesh(
    new THREE.PlaneGeometry(state.width * tilesAcross, state.height * tilesDeep),
    new THREE.MeshStandardMaterial({ map: groundTexture, color: '#b4b6a0', roughness: 1 }),
  );
  ground.name = 'Reach grassland';
  ground.rotation.x = -Math.PI / 2;
  ground.position.set((state.width - 1) / 2, 0, (state.height - 1) / 2);
  ground.receiveShadow = true;
  world.add(ground);
  terrainMesh = ground;
}

function makeCharacter(kind) {
  const group = new THREE.Group();
  group.userData.kind = kind;
  group.userData.animator = {
    landingDuration: .14,
    setState() {},
    update() {},
  };
  const playerCharacter = kind === 'player' || kind === 'player2';
  const label = kind === 'npc' ? 'MARA' : kind === 'player2' ? 'PATHFINDER' : 'WAYFARER';
  const color = kind === 'npc' ? '#e7c78b' : kind === 'player2' ? '#e3c7f2' : '#d3e1cb';
  group.userData.nameplate = makeNameplate(label, color, playerCharacter ? 1.78 : 1.82, kind !== 'player');
  group.add(group.userData.nameplate);
  addFallbackTraveler(group, kind);
  group.userData.appearance = {
    heightCm: 168,
    weightKg: 70,
    bustPercent: 100,
    stomachPercent: 100,
    hipsPercent: 100,
    glutesPercent: 100,
    thighsPercent: 100,
    skinTone: '#b17c5e',
    underwearTop: false,
    underwearBottom: false,
  };
  group.userData.displayName = label === 'WAYFARER' ? 'Wayfarer' : label;
  return group;
}

function addFallbackTraveler(group, kind) {
  const palette = kind === 'npc'
    ? { cloth: '#786044', trim: '#c49457', skin: '#bd866b', hair: '#40352c' }
    : kind === 'player2'
      ? { cloth: '#514d69', trim: '#a399c3', skin: '#bd9277', hair: '#40352c' }
      : { cloth: '#3d5e55', trim: '#bb9662', skin: '#ad795e', hair: '#302d29' };
  const cloth = material(palette.cloth, .92);
  const trim = material(palette.trim, .84, { metalness: .08 });
  const skin = material(palette.skin, .9);
  const hair = material(palette.hair, 1);
  const dark = material('#302f2a', 1);
  const add = (geometry, mat, position, options) => addMesh(group, geometry, mat, position, options);

  add(new THREE.CylinderGeometry(.29, .4, .9, 8), cloth, [0, .77, 0]);
  add(new THREE.CylinderGeometry(.28, .37, .17, 8), trim, [0, 1.16, 0]);
  add(new THREE.TorusGeometry(.3, .025, 6, 10), trim, [0, .52, 0], { rotation: [Math.PI / 2, 0, 0] });
  for (const side of [-1, 1]) {
    add(new THREE.CylinderGeometry(.07, .09, .28, 7), dark, [side * .13, .2, 0]);
    add(new THREE.BoxGeometry(.17, .13, .28), dark, [side * .13, .075, -.045]);
    add(new THREE.CylinderGeometry(.065, .085, .5, 7), cloth, [side * .35, .88, 0], { rotation: [0, 0, side * -.14] });
    add(new THREE.SphereGeometry(.075, 8, 6), skin, [side * .36, .61, -.015]);
  }
  add(new THREE.SphereGeometry(.145, 10, 8), skin, [0, 1.46, 0]);
  add(new THREE.SphereGeometry(.155, 10, 6, 0, Math.PI * 2, 0, Math.PI / 2), hair, [0, 1.49, 0]);
}

async function installTravelerModel(group, outfit) {
  const assetPath = travelerModelPaths[outfit];
  if (!assetPath || group.userData.modelPath === assetPath) return;
  group.userData.modelPath = assetPath;
  try {
    const gltf = await modelAssetLoader.load(assetPath);
    const model = gltf.scene;
    model.updateMatrixWorld(true);
    const bounds = new THREE.Box3().setFromObject(model);
    const size = bounds.getSize(new THREE.Vector3());
    if (!Number.isFinite(size.y) || size.y < .2) throw new Error(`Character model has invalid height: ${assetPath}`);
    const targetHeight = outfit === 'female' ? 1.68 : 1.74;
    const scale = targetHeight / size.y;
    model.scale.multiplyScalar(scale);
    model.position.set(-((bounds.min.x + bounds.max.x) * .5) * scale, -bounds.min.y * scale, -((bounds.min.z + bounds.max.z) * .5) * scale);
    model.userData.atlasBaseScale = scale;
    model.userData.atlasBaseHeightCm = Math.round(targetHeight * 100);
    model.userData.atlasBaseBounds = { min: bounds.min.clone(), center: bounds.getCenter(new THREE.Vector3()) };
    model.traverse(object => {
      if (!object.isMesh) return;
      object.castShadow = true;
      object.receiveShadow = true;
      if (object.material) {
        const cloneMaterial = material => {
          if (material.name !== 'Atlas · warm skin') return material;
          const cloned = material.clone();
          cloned.userData.atlasSkinMaterial = true;
          return cloned;
        };
        object.material = Array.isArray(object.material)
          ? object.material.map(cloneMaterial)
          : cloneMaterial(object.material);
      }
    });
    group.add(model);
    group.userData.characterModel = model;
    group.userData.modelPath = assetPath;
    if (group.userData.appearance.heightCm == null) group.userData.appearance.heightCm = Math.round(targetHeight * 100);
    if (!group.userData.appearance.skinTone) {
      model.traverse(object => {
        const materials = object.material ? (Array.isArray(object.material) ? object.material : [object.material]) : [];
        const skin = materials.find(material => material.userData.atlasSkinMaterial);
        if (skin) group.userData.appearance.skinTone = `#${skin.color.getHexString()}`;
      });
    }
    applyCharacterAppearance(group, group.userData.appearance);
    if (group === player) syncAppearanceControls(group);
    if (group === player && group.userData.shoulderGuardsEnabled) setShoulderGuards(group, true);
    const nameplate = group.userData.nameplate;
    if (nameplate) nameplate.position.y = targetHeight + .12;
    const animationSet = await loadTravelerAnimations();
    if (animationSet) {
      try {
        const clips = retargetAnimationClips(model, animationSet.sourceRig, animationSet.clips);
        group.userData.animator = new CharacterAnimationController(model, clips, {
          sourceStrideMeters: animationSet.strideMeters,
          targetScale: targetHeight / animationSet.sourceHeightMeters,
        });
      } catch (error) {
        console.warn(`Could not animate ${outfit} traveler model; leaving it in its rest pose.`, error);
      }
    }
  } catch (error) {
    group.userData.modelPath = null;
    console.error(`Could not load ${outfit} traveler model:`, error);
  }
}

function applyCharacterAppearance(character, appearance) {
  character.userData.appearance = { ...character.userData.appearance, ...appearance };
  const model = character.userData.characterModel;
  if (!model) return;
  const state = character.userData.appearance;
  const { atlasBaseScale, atlasBaseBounds } = model.userData;
  const heightCm = THREE.MathUtils.clamp(Number(state.heightCm) || 168, 150, 190);
  const weightKg = THREE.MathUtils.clamp(Number(state.weightKg) || 70, 45, 120);
  for (const [key, min, max] of [
    ['bustPercent', 70, 130], ['stomachPercent', 70, 140], ['hipsPercent', 80, 125],
    ['glutesPercent', 70, 130], ['thighsPercent', 80, 125],
  ]) state[key] = THREE.MathUtils.clamp(Number(state[key]) || 100, min, max);
  const baseHeightCm = model.userData.atlasBaseHeightCm || 168;
  const heightScale = heightCm / baseHeightCm;
  model.scale.set(atlasBaseScale * (1 + Math.max(0, weightKg - 70) * .0011), atlasBaseScale * heightScale, atlasBaseScale * (1 + Math.max(0, weightKg - 70) * .0007));
  model.position.set(
    -atlasBaseBounds.center.x * model.scale.x,
    -atlasBaseBounds.min.y * model.scale.y,
    -atlasBaseBounds.center.z * model.scale.z,
  );
  model.traverse(object => {
    if (object.material) {
      const materials = Array.isArray(object.material) ? object.material : [object.material];
      for (const material of materials) {
        if (material.userData.atlasSkinMaterial && state.skinTone) material.color.set(state.skinTone);
      }
    }
    if (object.morphTargetDictionary && object.morphTargetInfluences) {
      const light = object.morphTargetDictionary.Build_Light;
      const heavy = object.morphTargetDictionary.Build_Heavy;
      if (light != null) object.morphTargetInfluences[light] = Math.max(0, (70 - weightKg) / 25);
      if (heavy != null) object.morphTargetInfluences[heavy] = Math.max(0, (weightKg - 70) / 50);
      const proportionPairs = [
        ['bustPercent', 'Bust_Smaller', 'Bust_Larger', 70, 130],
        ['stomachPercent', 'Stomach_Flatter', 'Stomach_Fuller', 70, 140],
        ['hipsPercent', 'Hips_Narrower', 'Hips_Wider', 80, 125],
        ['glutesPercent', 'Glutes_Smaller', 'Glutes_Larger', 70, 130],
        ['thighsPercent', 'Thighs_Slimmer', 'Thighs_Fuller', 80, 125],
      ];
      for (const [stateKey, smallerName, largerName, minimum, maximum] of proportionPairs) {
        const smaller = object.morphTargetDictionary[smallerName];
        const larger = object.morphTargetDictionary[largerName];
        const value = state[stateKey];
        if (smaller != null) object.morphTargetInfluences[smaller] = value < 100 ? (100 - value) / (100 - minimum) : 0;
        if (larger != null) object.morphTargetInfluences[larger] = value > 100 ? (value - 100) / (maximum - 100) : 0;
      }
    }
  });
  const bra = model.getObjectByName('ATLAS_UNDERWEAR_BRA_V1');
  const briefs = model.getObjectByName('ATLAS_UNDERWEAR_BRIEFS_V1');
  if (bra) bra.visible = Boolean(state.underwearTop);
  if (briefs) briefs.visible = Boolean(state.underwearBottom);
  if (character.userData.nameplate) character.userData.nameplate.position.y = heightCm / 100 + .12;
}

function syncAppearanceControls(character) {
  const state = character.userData.appearance;
  const model = character.userData.characterModel;
  if (!state || !model) return;
  if (state.skinTone) $('#appearance-skin').value = state.skinTone;
  $('#appearance-height').value = String(state.heightCm);
  $('#appearance-height-value').textContent = `${state.heightCm} cm`;
  $('#appearance-weight').value = String(state.weightKg);
  $('#appearance-weight-value').textContent = `${state.weightKg} kg`;
  for (const [key, id, label] of [
    ['bustPercent', 'bust', 'Bust'], ['stomachPercent', 'stomach', 'Stomach'],
    ['hipsPercent', 'hips', 'Hips'], ['glutesPercent', 'glutes', 'Glutes'], ['thighsPercent', 'thighs', 'Thighs'],
  ]) {
    $(`#appearance-${id}`).value = String(state[key] ?? 100);
    $(`#appearance-${id}-value`).textContent = `${state[key] ?? 100}%`;
  }
  const bra = model.getObjectByName('ATLAS_UNDERWEAR_BRA_V1');
  const briefs = model.getObjectByName('ATLAS_UNDERWEAR_BRIEFS_V1');
  $('#underwear-top-toggle').disabled = !bra;
  $('#underwear-top-toggle').checked = Boolean(state.underwearTop);
  $('#underwear-bottom-toggle').disabled = !briefs;
  $('#underwear-bottom-toggle').checked = Boolean(state.underwearBottom);
  $('#shoulder-guard-toggle').checked = Boolean(state.shoulderGuards);
}

function setShoulderGuards(character, enabled) {
  const model = character.userData.characterModel;
  if (!model) {
    character.userData.shoulderGuardsEnabled = enabled;
    return;
  }
  character.userData.shoulderGuardsEnabled = enabled;
  if (character.userData.shoulderGuards) {
    character.userData.shoulderGuards.forEach(guard => { guard.visible = enabled; });
    return;
  }

  const material = new THREE.MeshStandardMaterial({ color: '#a97838', metalness: .72, roughness: .34 });
  const trim = new THREE.MeshStandardMaterial({ color: '#e0bf75', metalness: .78, roughness: .28 });
  const guards = [];
  for (const side of ['Left', 'Right']) {
    const bone = model.getObjectByName(`mixamorig:${side}Shoulder`);
    const shoulderJoint = model.getObjectByName(`mixamorig:${side}Arm`);
    if (!bone || !shoulderJoint) {
      console.warn(`Cannot fit shoulder guard: missing ${side} shoulder or arm bone`);
      continue;
    }
    model.updateWorldMatrix(true, true);
    const guard = new THREE.Group();
    const shell = new THREE.Mesh(new THREE.SphereGeometry(1, 16, 12), material);
    shell.scale.set(.16, .105, .15);
    shell.position.y = .025;
    shell.castShadow = true;
    const ridge = new THREE.Mesh(new THREE.BoxGeometry(.18, .025, .035), trim);
    ridge.position.set(0, .12, 0);
    ridge.castShadow = true;
    guard.add(shell, ridge);
    guard.position.copy(shoulderJoint.getWorldPosition(new THREE.Vector3()));
    guard.position.y += .015;
    shoulderJoint.attach(guard);
    guards.push(guard);
  }
  character.userData.shoulderGuards = guards;
  if (!enabled) guards.forEach(guard => { guard.visible = false; });
}

function makeNameplate(label,color,y,visible=true){
  const element=document.createElement('canvas');element.width=320;element.height=72;
  const g=element.getContext('2d');g.fillStyle='rgba(15,26,24,.78)';g.beginPath();g.roundRect(5,8,310,56,12);g.fill();
  g.strokeStyle='rgba(204,190,141,.65)';g.lineWidth=2;g.stroke();
  g.fillStyle=color;g.font='600 24px system-ui';g.textAlign='center';g.textBaseline='middle';g.letterSpacing='3px';g.fillText(label,160,37);
  const texture=new THREE.CanvasTexture(element);texture.colorSpace=THREE.SRGBColorSpace;
  const sprite=new THREE.Sprite(new THREE.SpriteMaterial({map:texture,transparent:true,depthTest:false}));
  sprite.position.set(0,y,0);sprite.scale.set(1.9,.43,1);sprite.renderOrder=5;sprite.visible=visible;
  return sprite;
}

function applyState(state) {
  const oldPlayer=game?.player;
  game=state;
  if (state.appearance) {
    const saved = state.appearance;
    player.userData.appearance = {
      ...player.userData.appearance,
      heightCm: saved.height_cm,
      weightKg: saved.weight_kg,
      skinTone: saved.skin_tone,
      bustPercent: saved.bust_percent,
      stomachPercent: saved.stomach_percent,
      hipsPercent: saved.hips_percent,
      glutesPercent: saved.glutes_percent,
      thighsPercent: saved.thighs_percent,
      underwearTop: saved.underwear_top,
      underwearBottom: saved.underwear_bottom,
      shoulderGuards: saved.shoulder_guards,
    };
    player.userData.shoulderGuardsEnabled = saved.shoulder_guards;
  }
  const groundedAtSurface = traveler => {
    const height = Number(traveler.height) || 0;
    const verticalVelocity = Number(traveler.vertical_velocity) || 0;
    const surface = sampleGroundHeight(traveler.x, traveler.y, state.surface_features);
    if (!Number.isFinite(height) || height > surface + 4 ||
        (traveler.grounded !== false && Math.abs(height - surface) > .01)) {
      traveler.height = surface;
      traveler.vertical_velocity = 0;
      traveler.grounded = true;
      traveler.vx = 0;
      traveler.vz = 0;
      return true;
    }
    if (traveler.grounded === false && verticalVelocity <= 0 && height <= surface + .01) {
      traveler.height = surface;
      traveler.vertical_velocity = 0;
      traveler.grounded = true;
      traveler.vx = 0;
      traveler.vz = 0;
      return true;
    }
    return false;
  };
  if (groundedAtSurface(state.player) && state.velocity) {
    state.velocity.x = 0;
    state.velocity.z = 0;
  }
  for (const traveler of state.players || []) groundedAtSurface(traveler);
  if(Number.isInteger(state.last_processed_input)){
    acknowledgedSequence=Math.max(acknowledgedSequence,state.last_processed_input);
    movementSequence=Math.max(movementSequence,state.last_processed_input);
    pendingInputs=acknowledgeInputs(pendingInputs,acknowledgedSequence);
    outgoingInputs=outgoingInputs.filter(frame=>frame.sequence>acknowledgedSequence);
  }
  const localName=state.active_player?.name||'Wayfarer';
  void installTravelerModel(player, 'female');
  if(player.userData.displayName!==localName){
    if(player.userData.nameplate){player.remove(player.userData.nameplate);player.userData.nameplate.material.map?.dispose();player.userData.nameplate.material.dispose();}
    player.userData.nameplate=makeNameplate(localName.toUpperCase(),localName==='Pathfinder'?'#e3c7f2':'#d3e1cb',1.67,false);
    player.add(player.userData.nameplate);player.userData.displayName=localName;
  }
  if(state.active_player)$('#region-label').textContent=`${state.active_player.name.toUpperCase()} · LOCAL WORLD`;
  const authoritativeVelocity=state.velocity||{x:0,z:0};
  player.userData.targetX=state.player.x;player.userData.targetZ=state.player.y;
  if(!initialStateLoaded){
    predictedVelocity.x=authoritativeVelocity.x;predictedVelocity.z=authoritativeVelocity.z;
    movementSequence=state.last_processed_input||0;
    acknowledgedSequence=movementSequence;
    player.position.set(state.player.x,state.player.height||0,state.player.y);
    predictedPosition.x=previousPredictedPosition.x=state.player.x;
    predictedPosition.z=previousPredictedPosition.z=state.player.y;
    verticalMotion={height:state.player.height||0,velocity:state.player.vertical_velocity||0,
      grounded:state.player.grounded!==false,jumpBuffer:0,coyoteTime:.1};
    player.rotation.y=Math.PI;targetPlayerYaw=Math.PI;
    initialStateLoaded=true;
  }else{
    positionCorrection.x=state.player.x-predictedPosition.x;
    positionCorrection.z=state.player.y-predictedPosition.z;
    predictedVelocity.x+=(authoritativeVelocity.x-predictedVelocity.x)*.18;
    predictedVelocity.z+=(authoritativeVelocity.z-predictedVelocity.z)*.18;
    verticalCorrection=(state.player.height||0)-verticalMotion.height;
    const vx=authoritativeVelocity.x,vz=authoritativeVelocity.z;
    if(Math.hypot(vx,vz)>.08)targetPlayerYaw=Math.atan2(vx,vz);
    else if(oldPlayer&&(oldPlayer.x!==state.player.x||oldPlayer.y!==state.player.y))targetPlayerYaw=Math.atan2(state.player.x-oldPlayer.x,state.player.y-oldPlayer.y);
  }
  renderHud();
}

function renderHud(){
  $('#player-name').textContent=(game.active_player?.name||'Wayfarer').toUpperCase();
  $('#inventory').textContent=game.inventory.lumen_reed;
  $('#reed-count').textContent=String(game.inventory.lumen_reed).padStart(2,'0');
  $('#coords').innerHTML=`X ${String(Math.round(game.player.x)).padStart(2,'0')} <span>·</span> Y ${String(Math.round(game.player.y)).padStart(2,'0')}`;
  $('#vitality').innerHTML=`${game.player_health} <em>/ 100</em>`;
  $('#vitality-meter').style.width=`${game.player_health}%`;
  $('#attunement').innerHTML=`${game.beacon_awake?1:0} <em>/ 1</em>`;
  $('#attune-meter').style.width=game.beacon_awake?'100%':'0%';
  $('#objective').textContent=game.beacon_awake?'A signal answers beyond the valley':game.mara_met?'Wake the Listening Beacon':'Find Mara along the western path';
  $('#objective-hint').textContent=game.beacon_awake
    ? 'A new signal has reached the valley.'
    : game.mara_met
      ? 'Bring the Listening Beacon to life.'
      : 'Speak with Mara to learn about the Listening Beacon.';
  $('#journal').innerHTML=game.journal.map((entry,i)=>`<div class="journal-entry"><i>${String(i+1).padStart(2,'0')}</i><span>${escapeHtml(entry)}</span></div>`).join('');
  $('#note-count').textContent=String(game.journal.length).padStart(2,'0');
  $('#beacon-state').textContent=game.beacon_awake?'SIGNAL RETURNED':'DORMANT';
  $('#beacon-copy').textContent=game.beacon_awake?'A second light answers from beyond the valley. The world has changed.':'A weathered signal tower waits beneath the eastern trees.';
  $('#beacon-card').classList.toggle('awake',game.beacon_awake);
  $('#beacon-action').disabled=game.beacon_awake;
  $('#beacon-action').innerHTML=game.beacon_awake?'The beacon is awake <span>✦</span>':'Wake the beacon <span>→</span>';
  $('#events').innerHTML=game.events.length?game.events.map(e=>`<button class="world-event" type="button" data-world-event="${escapeHtml(e.event_id)}" aria-label="Inspect ${escapeHtml(eventName(e.type))}"><time>#${String(e.sequence).padStart(3,'0')}</time><b>${escapeHtml(eventName(e.type))}</b><br>${escapeHtml(e.rationale)} · ${escapeHtml(e.source.kind)}</button>`).join(''):'<div class="empty-event">Your actions will leave a trace here.</div>';
  $('#traveler-count').textContent=String(game.players?.length||1).padStart(2,'0');
  $('#world-memory-count').textContent=String(game.events.length).padStart(2,'0');
  const recent=game.events
    .filter(event=>!['PlayerMoved','PlayerSessionReleased'].includes(event.type))
    .slice(-2)
    .reverse();
  $('#world-feed').innerHTML=recent.length?recent.map(event=>`<div class="feed-entry"><time>#${String(event.sequence).padStart(3,'0')}</time><b>${escapeHtml(eventName(event.type))}</b></div>`).join(''):'<span class="feed-empty">Your discoveries and choices will appear here.</span>';
}

function escapeHtml(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function eventName(type){return ({PlayerMoved:'Trail walked',PlayerSessionReleased:'Traveler paused',ResourceGathered:'Lumen reed gathered',NPCSpokenTo:'Mara was heard',BeaconAwakened:'Beacon awakened',CreatureDamaged:'Mossling encounter',PlayerGuarded:'Guard raised',PlayerDodged:'Attack evaded',CreatureReawakened:'Mossling returned',EntityCreated:'World entity added',RelationshipEstablished:'World relationship added'})[type]||type;}
const WALK_START_SPEED=.12;
const WALK_STOP_SPEED=.06;
const RUN_START_SPEED=3.05;
const RUN_STOP_SPEED=2.65;
function locomotionState(speed,grounded,verticalVelocity,landingRemaining,previousState){
  if(!grounded)return verticalVelocity>.15?'jump':'fall';
  if(landingRemaining>0)return 'land';
  // Keep small prediction/interpolation fluctuations from repeatedly starting
  // and fading locomotion clips around a single speed threshold.
  if(previousState==='run'&&speed>RUN_STOP_SPEED)return 'run';
  if(speed>RUN_START_SPEED)return 'run';
  if((previousState==='walk'||previousState==='run')&&speed>WALK_STOP_SPEED)return 'walk';
  if(speed>WALK_START_SPEED)return 'walk';
  return 'idle';
}

async function refresh(){
  const response=await authenticatedFetch('/api/state',{headers:{'Accept':'application/json'}});
  if(!response.ok){
    const payload=await response.json().catch(()=>({}));
    const error=new Error(payload.error||`The valley could not be reached (${response.status}).`);
    error.status=response.status;throw error;
  }
  applyState(await response.json());
}

function showConnectionError(message){
  $('#connection-message').textContent=message;
  $('#connection-overlay').hidden=false;
  $('#connection-retry').focus();
}
async function connectToWorld(){
  const retry=$('#connection-retry');retry.disabled=true;retry.textContent='Connecting…';
  try{
    const response=await authenticatedFetch('/api/state',{headers:{'Accept':'application/json'}});
    if(!response.ok){const payload=await response.json().catch(()=>({}));throw new Error(payload.error||`World state request failed (${response.status}).`);}
    const state=await response.json();
    if(!game)buildLandscape(state);
    applyState(state);cameraController.snap(player.position);
    $('#connection-overlay').hidden=true;
  }catch(error){
    console.error('Atlas world connection failed:',error);
    $('#connection-message').textContent=error.message||'The valley could not load. Try again in a moment.';
  }finally{retry.disabled=false;retry.textContent='Try again';}
}
$('#connection-retry').addEventListener('click',connectToWorld);

async function act(action){
  if(busy)return;busy=true;
  try{
    const options={method:'POST',headers:{'Content-Type':'application/json','Accept':'application/json'},body:JSON.stringify(action)};
    const delivered=action.type==='move'?await network.request('/api/action',options,{retry:true}):null;
    const response=delivered?.response||await authenticatedFetch('/api/action',options);
    const result=delivered?.payload||await response.json();
    if(!response.ok){
      if(action.type==='move'&&Array.isArray(action.frames)){
        const existing=new Set(outgoingInputs.map(frame=>frame.sequence));
        outgoingInputs=[...action.frames.filter(frame=>!existing.has(frame.sequence)),...outgoingInputs].sort((a,b)=>a.sequence-b.sequence);
      }
      showToast(result.error||'That action did not work.');return;
    }
    if(result.detail.dialogue)showToast(result.detail.dialogue);
    else if(result.event_type==='BeaconAwakened')showToast('The beacon sings. Something answers from beyond the valley.');
    else if(result.event_type==='ResourceGathered')showToast('+1 Lumen reed');
    if(action.type==='move'&&result.detail){
      const detail=result.detail;
      if(Number.isInteger(result.acknowledged_sequence)){
        acknowledgedSequence=Math.max(acknowledgedSequence,result.acknowledged_sequence);
        pendingInputs=acknowledgeInputs(pendingInputs,acknowledgedSequence);
      }
      const renderedBeforeCorrection={x:predictedPosition.x,z:predictedPosition.z};
      const renderedBeforeVertical=verticalMotion.height;
      predictedPosition.x=detail.x;predictedPosition.z=detail.z;
      predictedVelocity.x=detail.vx;predictedVelocity.z=detail.vz;
      verticalMotion={height:detail.height||0,velocity:detail.vertical_velocity||0,
        grounded:detail.grounded!==false,jumpBuffer:detail.jump_buffer||0,coyoteTime:detail.coyote_time??.1};
      for(const frame of pendingInputs)simulateMovementFrame(frame.input,frame.run,1/60,frame.jump);
      previousPredictedPosition.x=predictedPosition.x;previousPredictedPosition.z=predictedPosition.z;
      positionCorrection.x=renderedBeforeCorrection.x-predictedPosition.x;
      positionCorrection.z=renderedBeforeCorrection.z-predictedPosition.z;
      verticalCorrection=renderedBeforeVertical-verticalMotion.height;
      correctionDistance=Math.hypot(positionCorrection.x,positionCorrection.z);
      maxCorrectionDistance=Math.max(maxCorrectionDistance,correctionDistance);
      if(correctionDistance>1)largeCorrections++;
      game.player={x:detail.x,y:detail.z};game.velocity={x:detail.vx,z:detail.vz};
      if(Math.hypot(detail.vx,detail.vz)>.08)targetPlayerYaw=Math.atan2(detail.vx,detail.vz);
      renderHud();
    }else await refresh();
  }catch{
    if(action.type==='move'&&Array.isArray(action.frames)){
      const existing=new Set(outgoingInputs.map(frame=>frame.sequence));
      outgoingInputs=[...action.frames.filter(frame=>!existing.has(frame.sequence)),...outgoingInputs].sort((a,b)=>a.sequence-b.sequence);
    }
    showToast('The local world server is unavailable. Restart it and try again.');
  }
  finally{busy=false;}
}

function showToast(message){const el=$('#toast');el.textContent=message;el.classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>el.classList.remove('show'),2800);}

function setAmbientEnabled(enabled){ambientEnabled=enabled;$('#audio-toggle').setAttribute('aria-pressed',String(enabled));if(audioContext&&ambientBus)ambientBus.gain.setTargetAtTime(enabled ? .22 : 0,audioContext.currentTime,.35);}
function scheduleBirdCall(){
  clearTimeout(birdCallTimer);
  if(!audioContext)return;
  birdCallTimer=setTimeout(()=>{
    if(!audioContext)return;
    const now=audioContext.currentTime,base=850+Math.random()*500;
    for(let note=0;note<2;note++){
      const start=now+note*.19,oscillator=audioContext.createOscillator(),envelope=audioContext.createGain();
      oscillator.type='sine';oscillator.frequency.setValueAtTime(base*(note?1.32:1),start);
      oscillator.frequency.exponentialRampToValueAtTime(base*(note?1.18:.88),start+.24);
      envelope.gain.setValueAtTime(.0001,start);envelope.gain.exponentialRampToValueAtTime(.012,start+.035);envelope.gain.exponentialRampToValueAtTime(.0001,start+.31);
      oscillator.connect(envelope).connect(ambientBus);oscillator.start(start);oscillator.stop(start+.32);
    }
    scheduleBirdCall();
  },9000+Math.random()*12000);
}
function startAmbient(){
  if(!audioContext){
    const AudioContextClass=window.AudioContext||window.webkitAudioContext;if(!AudioContextClass)return;
    audioContext=new AudioContextClass();ambientBus=audioContext.createGain();ambientBus.gain.value=0;ambientBus.connect(audioContext.destination);
    const buffer=audioContext.createBuffer(1,audioContext.sampleRate*3,audioContext.sampleRate),samples=buffer.getChannelData(0);
    for(let i=0;i<samples.length;i++)samples[i]=(Math.random()*2-1)*.24;
    const wind=audioContext.createBufferSource();wind.buffer=buffer;wind.loop=true;
    const filter=audioContext.createBiquadFilter();filter.type='lowpass';filter.frequency.value=520;filter.Q.value=.35;
    const windGain=audioContext.createGain();windGain.gain.value=.12;wind.connect(filter).connect(windGain).connect(ambientBus);wind.start();
    const windLfo=audioContext.createOscillator(),windDepth=audioContext.createGain();windLfo.type='sine';windLfo.frequency.value=.055;windDepth.gain.value=.045;windLfo.connect(windDepth).connect(windGain.gain);windLfo.start();
    for(const [frequency,gainValue] of [[110,.035],[164.8,.022]]){const tone=audioContext.createOscillator(),gain=audioContext.createGain();tone.type='sine';tone.frequency.value=frequency;gain.gain.value=gainValue;tone.connect(gain).connect(ambientBus);tone.start();}
  }
  if(audioContext.state==='suspended')audioContext.resume();
  if(!birdCallTimer)scheduleBirdCall();
  setAmbientEnabled(ambientEnabled);
}

function movementInput(){
  const movement=inputManager.movement();
  const forward=movement.forward,strafe=movement.strafe;
  let x=0,z=0;
  if(forward||strafe){
    clickDestination=null;
    const cameraAngle=cameraController.yaw,cameraForwardX=-Math.sin(cameraAngle),cameraForwardZ=-Math.cos(cameraAngle);
    const cameraRightX=Math.cos(cameraAngle),cameraRightZ=-Math.sin(cameraAngle);
    x=forward*cameraForwardX+strafe*cameraRightX;z=forward*cameraForwardZ+strafe*cameraRightZ;
  }else if(clickDestination&&game){x=clickDestination.x-game.player.x;z=clickDestination.z-game.player.y;if(Math.hypot(x,z)<.2){clickDestination=null;x=0;z=0;}}
  const length=Math.hypot(x,z);if(length>1){x/=length;z/=length;}
  return {x,z,run:movement.run&&length>0};
}
function walkableAt(x,z){
  const playerObstacles=[...(game?.players||[]).filter(p=>!p.is_self).map(p=>({x:p.x,z:p.y,radius:.2}))];
  return !game?.terrain||walkablePosition(x,z,game.terrain,game.width,game.height,.2,[...(game.obstacles||[]),...playerObstacles]);
}

async function createLocalSession(){
  const response=await fetch('/api/session',{method:'POST',headers:{'Accept':'application/json'}});
  const payload=await response.json();
  if(!response.ok)throw new Error(payload.error||'No local traveler seat is available.');
  sessionToken=payload.session_token;sessionStorage.setItem('atlas.local.session',sessionToken);
}

window.addEventListener('pagehide',()=>{
  if(!sessionToken)return;
  const closingToken=sessionToken;
  sessionToken='';
  sessionStorage.removeItem('atlas.local.session');
  fetch('/api/session/close',{method:'POST',keepalive:true,headers:{'Content-Type':'application/json'},
    body:JSON.stringify({session_token:closingToken})}).catch(()=>{});
});

async function authenticatedFetch(url,options={}){
  const send=()=>fetch(url,{...options,headers:{...(options.headers||{}),'X-Atlas-Session':sessionToken}});
  let response=await send();
  if(response.status===401&&url!=='/api/session'){
    if(!sessionRecovery)sessionRecovery=createLocalSession().finally(()=>{sessionRecovery=null;});
    await sessionRecovery;response=await send();
  }
  return response;
}
function tickMovement(time){
  const lastFrame=outgoingInputs.at(-1);
  const changed=lastFrame&&(lastFrame.input.x!==lastSentInput.x||lastFrame.input.z!==lastSentInput.z||lastFrame.run!==lastSentInput.run);
    if(!busy&&outgoingInputs.length&&(changed||time>=nextInputAt)){
    const frames=outgoingInputs.splice(0,32);
    lastSentInput=frames.at(-1);nextInputAt=time+95;
    act({type:'move',sequence:frames.at(-1).sequence,frames});
  }
}

function simulateMovementFrame(input,run,dt,jumpPressed=false){
  const speed=run?4.2:2.5;
  const step=integrateMovement(predictedPosition,predictedVelocity,input,dt,speed);
  const canTraverse=(x,z)=>{
    if(!verticalMotion.grounded)return true;
    const rise=sampleGroundHeight(x,z,game.surface_features)-sampleGroundHeight(predictedPosition.x,predictedPosition.z,game.surface_features);
    const distance=Math.hypot(x-predictedPosition.x,z-predictedPosition.z);
    return rise<=MAX_STEP_UP&&(rise<=0||rise/Math.max(distance,1e-6)<=MAX_WALKABLE_GRADE);
  };
  if(canTraverse(step.position.x,predictedPosition.z)&&walkableAt(step.position.x,predictedPosition.z)){
    const from=sampleGroundHeight(predictedPosition.x,predictedPosition.z,game.surface_features),to=sampleGroundHeight(step.position.x,predictedPosition.z,game.surface_features);
    predictedPosition.x=step.position.x;predictedVelocity.x=step.velocity.x;
    if(verticalMotion.grounded&&from-to>LEDGE_DROP)verticalMotion.grounded=false;
    else if(verticalMotion.grounded)verticalMotion.height=to;
  }else predictedVelocity.x=0;
  if(canTraverse(predictedPosition.x,step.position.z)&&walkableAt(predictedPosition.x,step.position.z)){
    const from=sampleGroundHeight(predictedPosition.x,predictedPosition.z,game.surface_features),to=sampleGroundHeight(predictedPosition.x,step.position.z,game.surface_features);
    predictedPosition.z=step.position.z;predictedVelocity.z=step.velocity.z;
    if(verticalMotion.grounded&&from-to>LEDGE_DROP)verticalMotion.grounded=false;
    else if(verticalMotion.grounded)verticalMotion.height=to;
  }else predictedVelocity.z=0;
  verticalMotion=integrateVerticalMovement(verticalMotion,jumpPressed,dt,sampleGroundHeight(predictedPosition.x,predictedPosition.z,game.surface_features));
}
function updateNetworkHud(time){
  if(time-lastNetworkHudAt<150)return;lastNetworkHudAt=time;
  const hud=$('#network-debug');if(!hud||hud.hidden)return;
  hud.textContent=`NET ${network.profileName.toUpperCase()}  ·  RTT ${network.stats.ping.toFixed(0)} ms  ·  JIT ${network.stats.jitter.toFixed(0)} ms  ·  LOSS ${(network.lossRate*100).toFixed(1)}%  ·  RETRY ${network.stats.retries}  ·  PENDING ${pendingInputs.length}  ·  ACK ${acknowledgedSequence}  ·  CORR ${correctionDistance.toFixed(2)} m  ·  MAX ${maxCorrectionDistance.toFixed(2)} m  ·  >1m ${largeCorrections}`;
}
function selectNetworkProfile(profile){network.setProfile(profile);$('#network-debug').hidden=false;showToast(`Network simulation: ${profile.toUpperCase()}`);}
window.addEventListener('keydown',event=>{
  if(!game||['INPUT','TEXTAREA'].includes(document.activeElement.tagName))return;
  const key=event.key.toLowerCase();
  if(key==='escape'){
    $('#ai-chat-panel').hidden=true;$('#ai-chat-toggle').setAttribute('aria-expanded','false');
    if(!$('#memory-drawer').hidden)$('#close-memory').click();
    return;
  }
  if(key==='i'){openDrawer('satchel');return;}
  if(key==='k'){openDrawer('skills');return;}
  if(key==='j'){openDrawer('magic');return;}
  if(key==='m'){openDrawer('notes');return;}
  if(['1','2','3','4','5'].includes(key)){
    event.preventDefault();selectNetworkProfile(({1:'local',2:'good',3:'average',4:'bad',5:'loss'})[key]);return;
  }
  if(['w','a','s','d','shift'].includes(key)){clickDestination=null;startAmbient();return;}
  if(event.repeat)return;
});
$('#beacon-action').addEventListener('click',()=>act({type:'interact',target:'beacon'}));
const drawerPanels={satchel:['satchel-content','Inventory'],appearance:['appearance-content','Appearance'],skills:['skills-content','Skills'],magic:['magic-content','Magic'],notes:['notes-content','World memory']};
let appearanceSaveTimer = null;
let appearanceSavePending = false;
let appearanceSaveInFlight = false;
function queueAppearanceSave() {
  clearTimeout(appearanceSaveTimer);
  $('#appearance-save-status').textContent = 'Saving…';
  appearanceSaveTimer = setTimeout(() => {
    appearanceSavePending = true;
    void flushAppearanceSave();
  }, 350);
}
async function flushAppearanceSave() {
  if (appearanceSaveInFlight || !appearanceSavePending) return;
  appearanceSavePending = false;
  appearanceSaveInFlight = true;
  const state = player.userData.appearance;
  const appearance = {
    schema: 'atlas-character-profile/v1',
    height_cm: Math.round(state.heightCm),
    weight_kg: Math.round(state.weightKg),
    skin_tone: state.skinTone,
    bust_percent: Math.round(state.bustPercent),
    stomach_percent: Math.round(state.stomachPercent),
    hips_percent: Math.round(state.hipsPercent),
    glutes_percent: Math.round(state.glutesPercent),
    thighs_percent: Math.round(state.thighsPercent),
    underwear_top: Boolean(state.underwearTop),
    underwear_bottom: Boolean(state.underwearBottom),
    shoulder_guards: Boolean(state.shoulderGuards),
  };
  try {
    const response = await authenticatedFetch('/api/appearance', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
      body: JSON.stringify({ appearance }),
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.error || `Save failed (${response.status})`);
    $('#appearance-save-status').textContent = 'Appearance saved';
  } catch (error) {
    $('#appearance-save-status').textContent = 'Save failed · try changing a control again';
    console.error('Character appearance save failed:', error);
  } finally {
    appearanceSaveInFlight = false;
    if (appearanceSavePending) void flushAppearanceSave();
  }
}
function updateAppearance(patch) {
  applyCharacterAppearance(player, patch);
  queueAppearanceSave();
}
function openDrawer(section){
  const drawer=$('#memory-drawer'),opening=drawer.hidden||drawer.dataset.section!==section;
  drawer.dataset.section=section;drawer.hidden=!opening;
  for(const [key,[id]] of Object.entries(drawerPanels))$('#'+id).hidden=!opening||section!==key;
  $('#drawer-title').textContent=drawerPanels[section]?.[1]||'World memory';
  document.querySelectorAll('[data-drawer-section]').forEach(trigger=>{
    trigger.setAttribute('aria-expanded',String(opening&&trigger.dataset.drawerSection===section));
  });
  document.querySelectorAll('[data-drawer-tab]').forEach(tab=>tab.setAttribute('aria-current',String(tab.dataset.drawerTab===section&&opening)));
}
const appearanceHeight=$('#appearance-height');
const appearanceWeight=$('#appearance-weight');
appearanceHeight.addEventListener('input',event=>{
  const heightCm=Number(event.currentTarget.value);
  $('#appearance-height-value').textContent=`${heightCm} cm`;
  updateAppearance({heightCm});
});
appearanceWeight.addEventListener('input',event=>{
  const weightKg=Number(event.currentTarget.value);
  $('#appearance-weight-value').textContent=`${weightKg} kg`;
  updateAppearance({weightKg});
});
for (const [id, stateKey] of [['bust','bustPercent'],['stomach','stomachPercent'],['hips','hipsPercent'],['glutes','glutesPercent'],['thighs','thighsPercent']]) {
  $(`#appearance-${id}`).addEventListener('input', event => {
    const value = Number(event.currentTarget.value);
    $(`#appearance-${id}-value`).textContent = `${value}%`;
    updateAppearance({ [stateKey]: value });
  });
}
$('#appearance-skin').addEventListener('input',event=>updateAppearance({skinTone:event.currentTarget.value}));
$('#underwear-top-toggle').addEventListener('change',event=>updateAppearance({underwearTop:event.currentTarget.checked}));
$('#underwear-bottom-toggle').addEventListener('change',event=>updateAppearance({underwearBottom:event.currentTarget.checked}));
$('#shoulder-guard-toggle').addEventListener('change',event=>{
  setShoulderGuards(player,event.currentTarget.checked);
  player.userData.appearance.shoulderGuards = event.currentTarget.checked;
  queueAppearanceSave();
  showToast(event.currentTarget.checked?'Shoulder guards equipped':'Shoulder guards removed');
});
$('#satchel-action').addEventListener('click',()=>openDrawer('satchel'));
$('#skills-action').addEventListener('click',()=>openDrawer('skills'));
$('#magic-action').addEventListener('click',()=>openDrawer('magic'));
$('#memory-action').addEventListener('click',()=>openDrawer('notes'));
document.querySelectorAll('[data-drawer-tab]').forEach(tab=>tab.addEventListener('click',()=>openDrawer(tab.dataset.drawerTab)));
$('#ai-chat-toggle').addEventListener('click',()=>{const panel=$('#ai-chat-panel'),opening=panel.hidden;panel.hidden=!opening;$('#ai-chat-toggle').setAttribute('aria-expanded',String(opening));});
$('#ai-chat-close').addEventListener('click',()=>{$('#ai-chat-panel').hidden=true;$('#ai-chat-toggle').setAttribute('aria-expanded','false');});
$('#events').addEventListener('click',event=>{
  const entry=event.target.closest('[data-world-event]');
  if(entry)loadEventExplanation(entry.dataset.worldEvent);
});
$('#close-event-explanation').addEventListener('click',()=>{$('#event-explanation').hidden=true;});
$('#close-memory').addEventListener('click',()=>{
  $('#memory-drawer').hidden=true;
  document.querySelectorAll('[data-drawer-section]').forEach(trigger=>trigger.setAttribute('aria-expanded','false'));
  document.querySelectorAll('[data-drawer-tab]').forEach(tab=>tab.setAttribute('aria-current','false'));
});
$('#audio-toggle').addEventListener('click',()=>{startAmbient();setAmbientEnabled(!ambientEnabled);});

async function loadEventExplanation(eventId){
  const panel=$('#event-explanation');
  panel.hidden=false;
  $('#event-explanation-title').textContent='Loading event…';
  $('#event-explanation-rationale').textContent='Retrieving its saved evidence and source.';
  try{
    const response=await authenticatedFetch(`/api/reasoning?event=${encodeURIComponent(eventId)}`,{headers:{'Accept':'application/json'}});
    const explanation=await response.json();
    if(!response.ok)throw new Error(explanation.error||'The event explanation could not be loaded.');
    const record=explanation.event;
    const actor=explanation.entities.find(entity=>entity.id===record.actor_id);
    $('#event-explanation-title').textContent=`#${String(record.sequence).padStart(3,'0')} · ${eventName(record.type)}`;
    $('#event-explanation-rationale').textContent=record.rationale;
    $('#event-explanation-actor').textContent=actor?.attributes?.name||record.actor_id;
    $('#event-explanation-time').textContent=new Date(record.at).toLocaleString();
    $('#event-explanation-source').textContent=`${record.source.kind} · ${record.source.identifier}`;
    $('#event-explanation-result').textContent=JSON.stringify(record.detail,null,2);
  }catch(error){
    $('#event-explanation-title').textContent='Event explanation unavailable';
    $('#event-explanation-rationale').textContent=error.message||'Try again when the world reconnects.';
    $('#event-explanation-actor').textContent='';$('#event-explanation-time').textContent='';
    $('#event-explanation-source').textContent='';$('#event-explanation-result').textContent='';
  }
}

const viewSettings=$('#view-settings');
const viewToggle=$('#view-toggle');
const cameraControls={sensitivity:$('#camera-sensitivity'),zoomSpeed:$('#camera-zoom-speed'),smoothing:$('#camera-smoothing'),invertY:$('#camera-invert-y')};
for(const [name,control] of Object.entries(cameraControls)){
  const value=cameraController.settings[name];
  if(name==='invertY')control.checked=value;else control.value=String(value);
  control.addEventListener('input',()=>cameraController.setOption(name,name==='invertY'?control.checked:control.value));
}
function setViewSettings(open){
  viewSettings.hidden=!open;viewToggle.setAttribute('aria-expanded',String(open));
}
viewToggle.addEventListener('click',()=>setViewSettings(viewSettings.hidden));
$('#close-view-settings').addEventListener('click',()=>setViewSettings(false));

function resize(){
  const width=canvas.clientWidth,height=canvas.clientHeight;if(!width||!height)return;
  camera.aspect=width/height;camera.updateProjectionMatrix();renderer.setSize(width,height,false);
}
const resizeObserver=new ResizeObserver(resize);resizeObserver.observe(canvas.parentElement);window.addEventListener('resize',resize);

canvas.addEventListener('pointerdown',event=>{if(event.button!==0)return;startAmbient();clickPointer={id:event.pointerId,x:event.clientX,y:event.clientY};canvas.setPointerCapture(event.pointerId);});
canvas.addEventListener('pointerup',event=>{
  if(event.button!==0)return;
  const click=clickPointer;clickPointer=null;if(!click||click.id!==event.pointerId||Math.hypot(event.clientX-click.x,event.clientY-click.y)>5||!game)return;
  pointer.x=(event.clientX/canvas.clientWidth)*2-1;pointer.y=-(event.clientY/canvas.clientHeight)*2+1;
  raycaster.setFromCamera(pointer,camera);const hit=terrainMesh?raycaster.intersectObject(terrainMesh)[0]?.point:new THREE.Vector3();
  if(hit){
    clickDestination={x:THREE.MathUtils.clamp(hit.x,.3,game.width-.3),z:THREE.MathUtils.clamp(hit.z,.3,game.height-.3)};
  }
});

function animate(time){
  requestAnimationFrame(animate);
  const frameDelta=lastFrameTime?Math.min((time-lastFrameTime)/1000,.05):1/60;lastFrameTime=time;
  if(game){
    updateNetworkHud(time);
    const delta=frameDelta;
    const input=movementInput();
    movementClock.update(delta,stepDelta=>{
      previousPredictedPosition.x=predictedPosition.x;previousPredictedPosition.z=predictedPosition.z;
      const wasGrounded=verticalMotion.grounded;
      const jumpPressed=inputManager.justPressed(' ');
      simulateMovementFrame(input,input.run,stepDelta,jumpPressed);
      if(!wasGrounded&&verticalMotion.grounded){landingImpact=1;landingTime=player.userData.animator.landingDuration||.14;}
      if(Math.hypot(input.x,input.z)>.001||Math.hypot(predictedVelocity.x,predictedVelocity.z)>.03||!verticalMotion.grounded||jumpPressed){
        const frame={sequence:++movementSequence,timestamp:performance.now(),input:{x:input.x,z:input.z},run:input.run,jump:jumpPressed};
        pendingInputs.push(frame);outgoingInputs.push(frame);
      }
    });
    const renderAlpha=movementClock.alpha();
    positionCorrection.x*=Math.exp(-7*delta);positionCorrection.z*=Math.exp(-7*delta);verticalCorrection*=Math.exp(-9*delta);
    player.position.x=previousPredictedPosition.x+(predictedPosition.x-previousPredictedPosition.x)*renderAlpha+positionCorrection.x;
    player.position.z=previousPredictedPosition.z+(predictedPosition.z-previousPredictedPosition.z)*renderAlpha+positionCorrection.z;
    tickMovement(time);
    if(!busy&&!snapshotPollPending&&time>=nextSnapshotPollAt){
      nextSnapshotPollAt=time+100;snapshotPollPending=true;
      refresh().catch(error=>{if(error.status===409)showConnectionError(error.message);}).finally(()=>{snapshotPollPending=false;});
    }
    const speed=Math.hypot(predictedVelocity.x,predictedVelocity.z);
    player.userData.locomotionSpeed=speed;
    landingImpact*=Math.exp(-22*delta);landingTime=Math.max(0,landingTime-delta);
    const state=locomotionState(speed,verticalMotion.grounded,verticalMotion.velocity,landingTime,player.userData.locomotionState);
    player.userData.locomotionState=state;
    const yawDifference=Math.atan2(Math.sin(targetPlayerYaw-player.rotation.y),Math.cos(targetPlayerYaw-player.rotation.y));
    player.rotation.y+=yawDifference*(1-Math.exp(-8*delta));
    player.userData.animator.setState(state,speed,landingImpact);
    player.userData.animator.update(delta);
    const squash=landingImpact*.08;
    player.scale.set(1+squash*.45,1-squash,1+squash*.45);
    player.position.y=verticalMotion.height+verticalCorrection;
    cameraController.update(delta,player.position,inputManager.cameraIntent(),game.obstacles);
  }
  renderer.render(scene,camera);
}

scene.add(new THREE.AmbientLight('#d8d4bd',.24));
cameraController.snap(player.position);resize();
connectToWorld();
requestAnimationFrame(animate);
