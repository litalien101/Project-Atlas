# Character source models

This directory documents external geometry sources and repeatable local
acquisition. Large source binaries are kept in the ignored
`art/characters/.source_cache/` directory rather than committed to Git. Fetch
an exact, checksum-pinned copy with:

```sh
python3 tools/characters/download_reference_model.py troll-mauler
python3 tools/characters/download_reference_model.py blender-human-bases
```

## Troll Mauler

- **Download:** [OpenGameArt Troll Mauler](https://opengameart.org/content/troll-mauler)
- **Creator:** piacenti
- **License:** [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/); credit the creator and identify modifications when distributing a derivative.
- **Pinned source:** `troll.blend`, SHA-256 `83fc5e524d31020d8b7c9641517f965cecd65840b3119582b4e984649f708c51`.
- **Inspection:** Blender 2.73 source file; current Blender 5.2 opened it with a legacy-version warning. It contains a 2,999-vertex medium body mesh, a 749-vertex low mesh, a 33-bone armature, 47 body vertex groups, and packed 4K maps. The rendered preview is a hunched, brown troll with clothing; it is not the Atlas Stone Troll, is not in the required T-pose, and its rig/topology have not been approved for Atlas.
- **Use:** sculpting and topology workflow reference only until the design is adapted, cleaned, posed, and reviewed. Do not register it as a runtime asset or describe it as the generated Stone Troll.

## Blender Studio Human Base Meshes

- **Download:** [Blender Studio asset bundle](https://www.blender.org/download/demo-files/)
- **Creator:** Blender Studio and community contributors.
- **License:** CC0 1.0, as listed for Human Base Meshes v1.4.1 by Blender's asset-bundle page.
- **Pinned source:** `human-base-meshes-bundle-v1.4.1.zip`, SHA-256 `811f43accbb31a88266d932f8f5563b2d13586fca0ba2693aad1f5fe582b3515`.
- **Use:** optional topology/anatomy scaffold for authoring a new creature base. It is human anatomy, not a troll model, and requires sculpting and a project-specific T-pose/topology review.

## Acceptance boundary

These sources are authoring references, not approved Atlas assets. A candidate
Stone Troll base must match the approved design and pass the geometry-only
T-pose gate before texturing or surface-detail work begins. Materials, textures,
hair, skin detail, and runtime release are later pipeline stages; they are not
requirements for accepting the base-mesh stage.
