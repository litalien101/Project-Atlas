# Contributor and AI orientation

Read `README.md` first. Use the focused references below before changing a
subsystem; do not infer production readiness from a generated preview.

## Project map

- `atlas_server/`: local Python HTTP server, world/action rules, storage, and
  appearance profile validation.
- `web/`: browser client, Three.js rendering, UI, runtime asset manifest, and
  bundled browser output (`web/game.js`). Edit `web/app.js` and source modules;
  rebuild the bundle with `npm run build`.
- `art/characters/profiles/`: input design profiles, validated against
  `specs/atlas-character-design-profile-v1.schema.json`.
- `tools/characters/`: deterministic Blender generation, asset preparation,
  profile validation, base review, landmark placement, and asset checks.
- `art/characters/pending_models/` and `pending_equipment/`: review artifacts;
  not served by the game unless separately approved and registered.
- `web/assets/manifest.yaml`: runtime asset inventory, provenance, approval
  state, and checksums. Do not mark an asset cleared without recorded rights
  evidence.
- `specs/`: versioned data contracts and subsystem workflow documentation.

## Character pipeline

The repository does not call an AI API. The local Recipe Studio can compile a
small set of explicit text measurements and feature toggles into a Stone Troll
profile; qualitative prose is preserved but not guessed into geometry. A user
can also supply compact design-profile JSON. Blender scripts deterministically
generate or process the mesh. The stages are profile, recipe/build plan, base
generation, human base acceptance, texture/material authoring, landmark
placement, rig/weight review, animation, then separate runtime release review.
The runtime appearance save profile is distinct from the creator design
profile. Begin with `specs/atlas-character-generation.md` and follow its
commands and review gates.

Read `MASTER_FILE.md` for the current project architecture, implemented versus
planned features, and decisions. Update it with each substantial pipeline or
world-system implementation: revise status/roadmap entries and add a dated note
listing the change and verification performed. Keep it factual; do not mark a
planned capability as implemented.

The former `stone_troll` calibration was removed during the rights audit; do
not restore or use that source as troll geometry. Procedural generation creates
a low-detail blockout and requires `--allow-blockout`. An optional geometry-seed
path can adapt a separately calibrated `.glb` or `.blend` only after a human
attests rights, topology, and design fit; hash checks and that attestation do
not establish visual quality or production readiness. No current source is an
approved Stone Troll geometry seed. The pipeline has no high-detail mesh
generator. The image path uses local pixel measurements only; it cannot infer
hidden geometry, surface detail, or production topology. See
`specs/atlas-character-generation.md` for the source-seed workflow and limits.

## Useful commands

From the repository root:

```sh
npm ci
npm run build
python3 -m atlas_server
```

Character profile and asset checks:

```sh
npm run characters:profile-check -- art/characters/profiles/stone_troll.json
npm run assets:check
```

Run the deterministic authoring UI from the repository root with
`python3 tools/characters/recipe_studio_server.py`; it binds to loopback at
`http://127.0.0.1:8766` by default.

Blender generation requires Blender 4.x or newer with glTF support:

```sh
blender --background --python tools/characters/generate_character_base.py -- \
  --profile art/characters/profiles/stone_troll.json
```

The project test suites are available through `npm run ci`; review the README
and package scripts before running checks that alter generated outputs.

## Change and release rules

- Update the relevant spec/schema and README when changing a contract or
  workflow. Keep examples synchronized with actual tool behavior.
- Regenerate derived artifacts through their source scripts; do not hand-edit
  generated bundles, checksums, or model records without regenerating them.
- Keep source references, licenses, and provenance with derived art. Do not
  commit private or unlicensed source assets.
- A pending artifact is not runtime approved. Registration and release checks
  are explicit gates, not automatic consequences of generation.
- Preserve the active feature branch unless the user explicitly requests a
  merge or main-branch push.
