# Project Atlas: The Reach

The Reach is Atlas's first playable reference world. All player and traveler avatars now use one character model: the female base currently being developed. The project opens as a clean character sandbox on a flat, undecorated ground plane.

## Start here

For orientation, read this file and [`MASTER_FILE.md`](MASTER_FILE.md), the current project vision, architecture, status, and roadmap. [`AGENTS.md`](AGENTS.md) is the short contributor and AI guide. Read [`specs/atlas-character-generation.md`](specs/atlas-character-generation.md) for the character workflow and [`specs/asset-provenance.md`](specs/asset-provenance.md) for rights and release rules. The local game entry point is `atlas_server`; browser sources are in `web/`; character tools are in `tools/characters/`; runtime assets and checksums are under `web/assets/` and `web/assets/manifest.yaml`.

The character pipeline uses a compact design-profile JSON, deterministic Blender generation, human base review, landmark placement, then separate rigging/weighting and appearance stages. It does not call an AI service or create a finished rigged character. Work in `art/characters/pending_models/` and `pending_equipment/` is authoring/review data, not a runtime asset. Runtime activation requires explicit review and registration.

The first character quality target is the geometry-only mesh in the approved T-pose. Textures and fine surface details are later stages; passing the mesh gate is not production or runtime approval. Optional free modeling references and their exact licenses are documented in [`art/characters/sources/README.md`](art/characters/sources/README.md).

## Run locally

Requires Python 3.11 or newer and Node.js 20+. The Python server uses PyYAML to validate Atlas's YAML contracts; the browser client uses Three.js for rendering. Both projects use the permissive MIT license. Third-party notices are in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

```bash
cd Project_Atlas
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
npm ci
npm run build
python3 -m atlas_server
```

Open <http://127.0.0.1:8765>. The page opens as a focused character workbench with one female traveler and a pinned appearance panel. The panel adjusts skin tone, height, weight, bust, stomach, hips, glutes, thighs, optional underwear, and shoulder guards. The validated `atlas-character-profile/v1` profile is stored with the local traveler in SQLite and restored on reconnect. Proportion controls are hand-authored shape targets, not a scan-based fitting system. Other sessions and NPCs remain in world data but are hidden from this preview. The server-side world history and authoring APIs remain available.

To reset the save, stop the server and remove `data/world.sqlite3`.

### Imported 3D assets

The server serves model assets from `web/assets` by default. To serve a separate, curated model directory, set `ATLAS_ASSET_DIR` before starting the server:

```bash
ATLAS_ASSET_DIR=/path/to/models python3 -m atlas_server
```

Only supported model, animation, and image resources are served under same-origin `/assets/` URLs. Paths are confined to the configured directory; scripts, archives, and source-project files are not exposed. Keep glTF sidecars such as `.bin` and texture images beside their model at the relative paths recorded in the glTF file. Asset origins, licenses, modifications, and checksums are recorded in `web/assets/manifest.yaml`.

The glTF model loader accepts paths relative to the configured asset directory and returns a cloned scene plus any embedded clips:

```js
import { ModelAssetLoader } from './model_loader.js';

const modelLoader = new ModelAssetLoader();
const { scene, animations } = await modelLoader.load('characters/female_base_atlas_v1.glb');
world.add(scene);
```

All traveler instances use the female base at `female_base_atlas_v1.glb`. Its source body, optional underwear meshes, and customization targets share the 67-bone Mixamo rig. The bundled Mixamo idle, walk, run, jump, fall, and landing clips are loaded once and retargeted to the character's matching bone names. Root travel stays server-authoritative, walk/run timing follows movement speed, and transitions blend between states. The retargeter omits the hips rotation because the Blender glTF export applies an axis correction there; Atlas keeps root orientation and movement in control. Shape controls currently change the matching hand-authored morph targets on the body and garments. See `web/assets/manifest.yaml` for asset checksums and provenance.

For new Blender clothing assets, see [`specs/atlas-clothing-authoring.md`](specs/atlas-clothing-authoring.md) and run `tools/characters/prepare_clothing_asset.py` to transfer Atlas bone weights and body morphs and export a skinned GLB.

### Text-to-character generation

The creator workflow uses a compact, validated [`atlas-character-design-profile/v1`](specs/atlas-character-design-profile-v1.schema.json) contract. The current Blender generator makes low-detail concept blockouts; it has no high-detail text-to-3D backend. Blockout generation now requires `--allow-blockout`, and the review gate will not accept one as a rigging candidate until it has been manually sculpted and reviewed. A front-view image can adjust silhouette width, but it cannot supply hidden geometry, surface detail, or production topology. The Stone Troll's licensed calibration is measurement-only because its source model does not match the requested design. See [`specs/atlas-character-generation.md`](specs/atlas-character-generation.md) for the actual limits and review gates.

Run `npm run assets:check` to validate the registered runtime asset paths and SHA-256 checksums, GLB skin structure, and consistency between the female base and humanoid rig contracts. New clothing exports include a runtime checksum and remain marked for fit review and rights review until those gates are completed. `npm run assets:release-check` additionally fails unless every registered asset has `redistribution_status: cleared`; do not clear that field without documenting the applicable redistribution terms. The automated check does not replace the required visual preview through idle, walk, run, jump, fall, and land.

The female character's rig-weighted region map lives in `art/characters/atlas_female_base_v1/atlas_body_regions_v1.json`. Rebuild it after a base-model change with `blender --background --python tools/characters/build_body_region_schema.py`. Clothing preparation requires explicit `--region` values and writes to `art/characters/pending_equipment/`; pending exports are not runtime-visible. After inspecting every morph extreme and all six locomotion states, register clothing with `npm run assets:register-clothing -- --help`. Registration requires a completed fit checklist, a named reviewer, and explicit rights evidence. The server serves clothing only when the registry marks it approved and its checksum matches.

The character sandbox uses a level 40×14 walkable area with no static scenery colliders.

### Network development controls

Use **1–5** while playing to switch the movement request simulator: **1** local, **2** good (50 ms), **3** average (120 ms), **4** bad (250 ms), and **5** packet-loss mode (10%). The debug strip reports RTT, jitter, simulated loss, retries, queued acknowledgements, and reconciliation correction. The simulator retries sequenced fixed-tick movement batches; duplicate retries are idempotent on the server. This is a local HTTP stress tool, not a packet-driven multiplayer transport.

Run `npm run ci` for deterministic JavaScript network/property-style checks, Python movement and rewind checks, and a client build. Both runtimes consume `tests/fixtures/movement-contract.json` to verify the same 60 Hz acceleration, diagonal-run, stop, and terrain-footprint behavior. The test setup uses Node's built-in runner instead of adding Jest or property-testing packages to this small JavaScript project. Gameplay and NPC state remain server-side prototypes; the browser currently renders the female character alone for model work.

## What this proves

- The server validates and applies actions; the browser only renders state and sends intent.
- Startup validates the seeded Player, NPC, Region, Building, ResourceNode entities and their relationships against the bundled Atlas ontology and schema registry in `specs/atlas/specs`.
- SQLite stores the ontology-validated entity graph; creator-authored entity and relationship writes are committed with immutable provenance events.
- The local knowledge and memory queries return linked entities, event IDs, actors, source references, timestamps, and authored rationale.
- Every accepted game event is validated as a registered Atlas `Event` entity and its action relationship is checked against the ontology.
- World state persists in SQLite.
- Each accepted action appends an immutable event in the same transaction as the state update.
- The event history records schema version, actor, source, affected object IDs, and rationale; it can rebuild current state.
- The beacon activation is a creator-authored deterministic world change, not an AI-generated claim.
- The client is a working game loop, not an Atlas platform or production MMO service.

### Local world authoring and explanation API

The loopback server exposes the first creator-authored world-model slice. Add an entity with a canonical UUID, registered ontology type, timezone-aware `created_at`, a source reference, and an authored rationale:

```json
{
  "entity": {
    "id": "a UUID",
    "type": "NPC",
    "created_at": "2026-10-02T12:00:00Z",
    "name": "Ilyra the Cartographer"
  },
  "source": { "kind": "creator_edit", "identifier": "a UUID" },
  "rationale": "Added a cartographer to explain the eastern road network."
}
```

Send that body to `POST /api/entities`. Then establish an ontology-declared edge with `POST /api/relationships`, using `type`, `source_id`, `target_id`, `source`, and `rationale`. Each request writes its immutable event and entity/relationship projection in one SQLite transaction. Repeated entity IDs, duplicate authored edges, unknown types, missing endpoints, or invalid relation directions are rejected without partial writes.

`GET /api/knowledge?source=<uuid>&target=<uuid>&type=located_in` explains matching edges and includes both entity records, the source event, actor, source reference, timestamp, and rationale. `GET /api/memory?entity=<uuid>&after=<sequence>` returns matching immutable history in sequence order. Read queries require the local traveler session header used by `/api/state`; authoring is restricted to the loopback server and same-origin requests. The API is a development interface, not a public creator service.

`GET /api/analytics?after=<sequence>&limit=1000` aggregates a bounded page of observed event history: activity by event/actor and date, social interactions, progression milestones, resource inflow/outflow, and combat outcomes. It reports formulas as direct counts and explicitly marks retention and causal explanation unavailable; analytics does not generate recommendations or claims.

`POST /api/appearance` saves a complete `atlas-character-profile/v1` document for the authenticated local traveler. `GET /api/state` returns that traveler’s saved `appearance`; the profile is validated against [`atlas-character-profile-v1.schema.json`](specs/atlas-character-profile-v1.schema.json) before its SQLite projection is updated. Appearance is a cosmetic profile update and does not append a world gameplay event.

`POST /api/simulations` runs the deterministic `resource_progression` model against recorded lumen-reed and beacon events. Send `{"proposed_change":{"rule":"beacon.lumen_reed_cost","value":2}}` with the local traveler session header. The saved response includes baseline and candidate replays, evidence event IDs, scope-limited confidence, risk, and model limitations. Fetch a saved result with `GET /api/simulations/<simulation_uuid>`. A simulation is an immutable analysis artifact: it does not edit world rules, world projections, or event history. It replays observed activation attempts only; it cannot infer failed attempts or predict player choices. Stochastic predictions, if added later, must use separate models with independent seeded runs rather than counting repeated deterministic replays as evidence.

`POST /api/policy/evaluations` accepts `{"simulation_id":"<simulation_uuid>"}` and evaluates that saved simulation against [`atlas-policy-engine.yaml`](specs/atlas/specs/atlas-policy-engine.yaml). The policy rejects cost changes over the creator-defined 10% limit, high-risk projections, insufficient recorded outcomes, confidence below 0.85, and rule changes without an explicit policy. Results are immutable and retrievable from `GET /api/policy/evaluations/<evaluation_uuid>`. An eligible result means the change may be presented for human review; it is not approval and does not alter the world. No autonomous world changes are enabled.

`POST /api/decisions` accepts both the persisted `simulation_id` and its matching `evaluation_id`. The decision record combines the proposal, policy outcome, simulation confidence and scope, affected entities, and evidence references. It recommends approval only when the policy gate passes; that state is `awaiting_human_approval`. A blocked policy result produces a rejection recommendation with the violations. Records are immutable and readable from `GET /api/decisions/<decision_uuid>`.

Record a human choice with `POST /api/decisions/<decision_uuid>/review`, sending `{"action":"approve","rationale":"Reviewed the evidence and accept this proposal."}`. Supported actions are `approve`, `reject`, `delay`, and `escalate`; each decision accepts one review with a required rationale. Approval changes the decision to `approved_pending_deployment`, while the response still confirms `world_change_applied: false`. Deployment remains a distinct capability and is not yet implemented.

`GET /api/reasoning?event=<uuid>` returns the authored rationale, recorded result, involved entities, and any relationship written by that event. This provenance trace carries no inferred confidence and does not create a `TruthRecord`. Derived claims remain gated by two distinct evidence references, validation, and confidence of at least 0.80 under `atlas-truth-model.yaml`; creator/player-authored event rationales are never treated as inferred causes.

## Architecture

```text
Browser client  ->  local HTTP API  ->  action rules  ->  SQLite transaction
      ^                                                    ├── current projection
      └──────────────── state query  <-───────────────────└── append-only event source
```

The project uses permissively licensed libraries and original procedural game geometry. It does not package assets from the reference RSPS cache. It makes no external service or AI calls; its analytics are local aggregates over the project’s own immutable event history. It binds to loopback by default. Local tab sessions are ephemeral seat assignments, not real player accounts. This is a local foundation demo, not safe to expose to the public internet or use for real player accounts.

The two-player local session, state ownership, and per-player tick rules are in [`specs/local-multiplayer.md`](specs/local-multiplayer.md).
The game-to-ontology mapping and event relationships are documented in [`specs/reach-world-model.md`](specs/reach-world-model.md).
The art and asset reuse rules are in [`specs/asset-provenance.md`](specs/asset-provenance.md).
The world’s palette, lighting, composition, camera, and sound goals are in [`specs/visual-direction.md`](specs/visual-direction.md).

## Next foundation milestone

Before online multiplayer, replace local seat assignment with durable account/session credentials, add server-driven tick scheduling and a persistent transport, and define reconnection and presence behavior. Colyseus remains deferred until that remote-play milestone. Rapier was evaluated but is not part of the movement stack: the current scene has a small static grid, and introducing separate JS/Python physics bindings would add version and parity risk without solving a current obstacle-collision requirement. Revisit it when the world gains authored 3D colliders, slopes, or moving rigid bodies. The bundled ontology and schema registry are the contracts this game slice validates; they do not replace the broader Atlas evidence and policy contracts.

## License policy

The application code is original. Third-party libraries use permissive licenses whose notices are included in `THIRD_PARTY_NOTICES.md`. The project owner should choose and add a license for distributing Atlas source code; until then, assume its source is not granted for reuse.
