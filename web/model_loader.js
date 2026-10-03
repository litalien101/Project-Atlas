import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { clone as cloneSkinnedScene } from 'three/addons/utils/SkeletonUtils.js';

const MODEL_EXTENSIONS = new Set(['.gltf', '.glb']);
// Bump this whenever a bundled character asset changes, so cached large GLBs
// from older releases cannot mask the optimized versions.
const MODEL_ASSET_REVISION = '10';

export function modelAssetUrl(assetPath) {
  if (typeof assetPath !== 'string' || assetPath.length === 0 || assetPath.includes('\\') || assetPath.includes('\0')) {
    throw new TypeError('Model asset paths must be non-empty relative paths.');
  }

  const segments = assetPath.split('/');
  if (segments.some(segment => segment === '' || segment === '.' || segment === '..')) {
    throw new TypeError('Model asset paths cannot contain empty or traversal segments.');
  }

  const extension = assetPath.slice(assetPath.lastIndexOf('.')).toLowerCase();
  if (!MODEL_EXTENSIONS.has(extension)) {
    throw new TypeError('Only glTF and GLB model assets can be loaded.');
  }

  return `/assets/${segments.map(encodeURIComponent).join('/')}`;
}

export class ModelAssetLoader {
  #loader;
  #cloneScene;
  #assets = new Map();

  constructor({ loader = new GLTFLoader(), cloneScene = cloneSkinnedScene } = {}) {
    this.#loader = loader;
    this.#cloneScene = cloneScene;
  }

  async load(assetPath) {
    const url = `${modelAssetUrl(assetPath)}?v=${MODEL_ASSET_REVISION}`;
    let pending = this.#assets.get(url);
    if (!pending) {
      pending = this.#loadWithRetry(url);
      this.#assets.set(url, pending);
    }

    try {
      const gltf = await pending;
      const sourceScenes = gltf.scenes ?? [gltf.scene];
      if (!gltf.scene || !sourceScenes.includes(gltf.scene)) {
        throw new Error(`The glTF asset has no active scene: ${assetPath}`);
      }

      const scenes = sourceScenes.map(scene => this.#cloneScene(scene));
      return { ...gltf, scene: scenes[sourceScenes.indexOf(gltf.scene)], scenes };
    } catch (error) {
      if (this.#assets.get(url) === pending) this.#assets.delete(url);
      throw error;
    }
  }

  async #loadWithRetry(url) {
    for (let attempt = 0; ; attempt++) {
      try {
        return await this.#loader.loadAsync(url);
      } catch (error) {
        const transient = /\b5\d{2}\b|failed to fetch|failed to load (?:texture|buffer)|networkerror|couldn't load (?:texture|buffer)/i.test(error?.message || '');
        if (!transient || attempt >= 2) throw error;
        await new Promise(resolve => setTimeout(resolve, 150 * (attempt + 1)));
      }
    }
  }
}
