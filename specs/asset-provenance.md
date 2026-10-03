# Game asset provenance policy

## Decision for The Reach

The workspace credit list is [`../ASSET_ATTRIBUTIONS.md`](../ASSET_ATTRIBUTIONS.md); source-library status and removals are tracked in [`../../Reference_Assets/ASSET_LICENSE_REGISTER.md`](../../Reference_Assets/ASSET_LICENSE_REGISTER.md). Atlas voluntarily credits CC0 sources as well as meeting licenses that require attribution.

The previous browser character prototype and derived clothing assets were removed on 2026-10-03 because their ownership and reuse rights were not documented. There is currently no registered Atlas character model in the runtime manifest; appearance controls and animation plumbing are not evidence of a usable character asset. The world is rendered with Three.js, whose code is under MIT; it supplies rendering functionality, not game assets.

Do not extract or package models, textures, animations, maps, sounds, or other game data from the RuneAi cache or Darkan reference client in this project. The local RuneAi repository contains a 601 MB `main_file_cache.dat2` plus cache indexes and a hash manifest, but the inspected cache files do not establish a reuse license. The vendored Darkan client and server source trees identify GPL-3.0; their source license does not establish rights to separately bundled game cache assets. Cleaning, retopologizing, recoloring, or converting an asset does not establish permission to reuse its underlying content.

Those repositories may inform broad genre conventions and technical lessons. Do not copy their distinctive character designs, world layouts, UI art, names, or extracted content into The Reach.

## Future imported asset gate

Before importing any non-original asset, record and review:

- Asset identifier and file checksum.
- Creator and original source URL.
- Exact license or written permission, including commercial use and modification rights.
- Required attribution and redistribution conditions.
- Modifications made and the person who made them.

Reject assets whose ownership or reuse terms cannot be verified. Prefer original commissioned or authored assets and permissively licensed assets with clear source files. Store this record beside the asset under `web/assets/manifest.yaml`.

## Removed Mixamo clips

The six raw Mixamo FBX clips were removed from the repository on 2026-10-03.
Adobe's [FAQ](https://helpx.adobe.com/creative-cloud/faq/mixamo-faq.html)
permits game use, but the project no longer needs raw source files in its public
repository while it has no approved character mesh.
Adobe's [Additional Terms](https://wwwimages2.adobe.com/content/dam/cc/en/legal/servicetou/Mixamo-Addl-Terms-en_US-20210623.pdf)
also prohibit using Mixamo services, content, data, or output to create, train,
test, or improve AI/ML systems. Do not add Mixamo material to recipe-learning
datasets or model training.
