# Game asset provenance policy

## Decision for The Reach

The Reach currently uses the user-provided female base in `female_base_atlas_v1.glb`, with underwear stored as separate rigged equipment meshes. The body and matching garments have hand-authored shape targets for weight, bust, stomach, hips, glutes, and thighs. The source blend and underwear archive are retained under `art/characters/atlas_female_base_v1`; runtime checksums and provenance are recorded in the asset manifest. License and redistribution terms for user-provided character assets have not been independently documented. The world is rendered with Three.js, whose code is under MIT; it supplies rendering functionality, not game assets.

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

## Mixamo animation pack

The six selected Action Adventure Pack animations were supplied in the project workspace by the project owner and are used as embedded animation content in the playable reference game. Adobe's Mixamo FAQ says characters and animations may be used royalty-free in personal, commercial, and non-profit projects, including video games. Preserve the source and checksums in the asset manifest, and do not package or offer the raw animation files as a standalone asset pack. Review Adobe's current [Mixamo FAQ](https://helpx.adobe.com/creative-cloud/faq/mixamo-faq.html) and applicable terms before distributing a build.
