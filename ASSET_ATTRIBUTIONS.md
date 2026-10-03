# Asset attributions and licenses

This is the project-facing credit list for third-party art assets and references. We credit creators even when their license does not require attribution. Credits do not mean an asset is approved for runtime use, and credit alone does not grant rights.

For third-party software dependencies, see [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md). For retained source files and the quarantine/removal history, see the [workspace asset license register](../Reference_Assets/ASSET_LICENSE_REGISTER.md) and [`/srv/source_models/README.md`](../../source_models/README.md).

## Verified art assets and references

### Blender Studio Human Base Meshes v1.4.1

**Preferred credit:** Blender Studio and community contributors, *Human Base Meshes v1.4.1*. Source: [Blender demo files](https://www.blender.org/download/demo-files/). License: [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/). The CC0 dedication does not require attribution; Atlas includes this credit by choice.

**Retained at:** `/srv/source_models/characters/humanoids/blender-human-bases/`. The source archive and extracted library checksums are recorded in [`/srv/source_models/metadata/catalog.json`](../../source_models/metadata/catalog.json). This is an authoring reference only. The current Stone Troll candidate was generated procedurally and does not contain this source mesh.

### OpenGameArt CC0 base and creature references

Atlas credits the following creators even though CC0 does not require attribution. Each source is listed as CC0 on its linked OpenGameArt page; per-file checksums and local locations are in [`/srv/source_models/metadata/catalog.json`](../../source_models/metadata/catalog.json).

- DaemonOutcast, *Human and Furry Base Meshes - DaemonBase*: [source page](https://opengameart.org/content/human-and-furry-base-meshes-daemonbase), CC0 1.0.
- Tyrfing, *Hydrach*: [source page](https://opengameart.org/content/hydrach), CC0 1.0.
- Shingox, *Low Poly Male Base Mesh*: [source page](https://opengameart.org/content/low-poly-male-base-mesh), CC0 1.0.
- Shingox, *Humanoid Low Poly Mesh (With Basic Face)*: [source page](https://opengameart.org/content/humanoid-low-poly-mesh-with-basic-face), CC0 1.0.
- GoldenThumbs, *Feminine Humanoid Base Mesh*: [source page](https://opengameart.org/content/feminine-humanoid-base-mesh), CC0 1.0.

These are authoring references only and are not part of the current Stone Troll candidate or runtime registry.

### Troll Mauler

**Preferred credit:** piacenti, *Troll Mauler*, via [OpenGameArt](https://opengameart.org/content/troll-mauler), [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/). If a derivative is distributed, include the creator/source/license credit and identify changes. No changes are made to the retained reference. This is an authoring reference only; its geometry is not used in the current Stone Troll candidate.

The checksum-pinned source is in the ignored local cache described in [`art/characters/sources/README.md`](art/characters/sources/README.md). Do not package it as a runtime asset.

### MakeHuman starter characters

**Preferred credit:** MakeHuman Community contributors, *MakeHuman system assets* (CC0 1.0 assets); generated with [MPFB](https://github.com/makehumancommunity/mpfb2) 2.0.17. Sources: [MakeHuman asset license](https://static.makehumancommunity.org/about/license.html) and [system asset pack](https://static.makehumancommunity.org/assets/assetpacks/makehuman_system_assets.html). Credit is included by choice for the CC0 assets. MPFB and Blender are authoring tools; their software licenses are separate from the generated asset license.

**Retained at:** [`/srv/projects/Reference_Assets/model_library/makehuman/`](../Reference_Assets/model_library/makehuman/). These are reference starters, not registered runtime assets.

## Current runtime status

[`web/assets/manifest.yaml`](web/assets/manifest.yaml) is empty. No third-party art asset is currently registered for the game. Generated Atlas work remains candidate-only until it passes its review and release gates.
