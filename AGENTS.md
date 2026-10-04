# Contributor and AI orientation

## Concurrent AI work coordination (required)

Before editing Project Atlas, read `/srv/current_status/README.md` and run
`python3 /srv/current_status/atlas_coord.py show` to inspect live work claims.
The coordination database is `/srv/current_status/atlas_coord.sqlite3`; the
legacy JSON snapshot is not the live state. Register the task's exact file
paths and semantic contract IDs with `/srv/current_status/atlas_coord.py claim`.
Contract claims cover shared data models, APIs, events, persistence formats,
and invariants, including changes made in files owned by another task. If a
file or contract overlap is reported, wait or narrow the task to independent
work. Update scopes, status, context, and next action as they change; heartbeat
active or waiting work. Release claims when the handoff is complete. Follow
the coordination guide for Git, documentation ownership, and quality rules.

Read `README.md` first. Use the focused references below before changing a
subsystem; do not infer production readiness from a generated preview.

## Project map

- `atlas_server/`: local Python HTTP server, world/action rules, storage, and
  appearance profile validation.
- `web/`: browser client, Three.js rendering, UI, runtime asset manifest, and
  bundled browser output (`web/game.js`). Edit `web/app.js` and source modules;
  rebuild the bundle with `npm run build`.
- `art/characters/profiles/`: input design profiles, validated against
  `specs/atlas-character-design-profile-v2.schema.json`.
- `tools/characters/`: deterministic Blender generation, asset preparation,
  profile validation, base review, landmark placement, and asset checks.
- `art/characters/pending_models/` and `pending_equipment/`: review artifacts;
  not served by the game unless separately approved and registered.
- `web/assets/manifest.yaml`: runtime asset inventory, provenance, approval
  state, and checksums. Do not mark an asset cleared without recorded rights
  evidence.
- `specs/`: versioned data contracts and subsystem workflow documentation.

## Character pipeline

Atlas uses a local, deterministic authoring workflow. The current baseline is a
neutral parametric humanoid profile; it is technical scaffolding, not the new
character design. The Recipe Studio maps only explicit supported measurements.
Blender produces review blockouts; it does not generate production topology,
materials, a rig, weights, or animation. Keep design intent, observed reference
data, generated candidates, review decisions, and runtime assets as separate
artifacts.

Before changing a stage, update its versioned schema and workflow documentation.
Preserve source hashes and license evidence for any reference input. A candidate
remains outside the runtime registry until visual review and release checks pass.
Do not claim that the observation intake is a trained model or that authored
rules were learned from data. Begin with `specs/atlas-character-generation.md`.

## Useful commands

From the repository root:

```sh
npm ci
npm run build
python3 -m atlas_server
```

Character profile and asset checks:

```sh
npm run characters:profile-check -- art/characters/profiles/starter_humanoid.json
npm run assets:check
```

Run the deterministic authoring UI from the repository root with
`python3 tools/characters/recipe_studio_server.py`; it binds to loopback at
`http://127.0.0.1:8766` by default.

Blender generation requires Blender 4.x or newer with glTF support:

```sh
blender --background --python tools/characters/generate_character_base.py -- \
  --profile art/characters/profiles/starter_humanoid.json
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
