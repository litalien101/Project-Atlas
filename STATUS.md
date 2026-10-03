# Project Atlas Implementation Status

## Current status

### Implemented pipeline inventory

- **Profiles and recipes:** `atlas-character-design-profile/v1` has a JSON
  Schema and Python validator. `compile_character_recipe.py` applies the
  authored grammar, scales supported proportions, carries relationships/tags,
  and records profile and grammar hashes. Draft archetype rules require an
  explicit opt-in. `compile_character_geometry_plan.py` validates the
  profile/recipe pair and freezes supported geometry inputs, snapshots, hashes,
  T-pose, and the no-rig requirement into a candidate build plan. Cross-recipe
  discovery is not connected to this compiler.
- **Full model recipe contract:** `atlas-model-recipe-v1.schema.json` specifies
  cross-category build inputs, dimensions, transforms, materials, rig/weight
  references, UV policy, material assignments, motion clips, variants,
  collision, LOD/performance budgets, provenance, QA, and checksummed outputs.
  It is schema groundwork only; no current generator executes this contract.
- **Text-to-recipe UI:** `recipe_studio_server.py` serves a loopback-only,
  chat-style workbench. `deterministic_recipe_compiler.py` maps a limited set
  of explicit measurements and feature toggles into the Stone Troll profile;
  unparsed prose is preserved but does not silently alter geometry. The UI
  compiles a character recipe/build plan and can run Blender to create a
  blockout candidate. There is no general natural-language parser or AI
  recipe service.
- **Prompt-to-recipe orchestration:** The broader workflow is documented in
  the creator-to-runtime section. A full-contract build-plan compiler,
  multi-archetype templates, general stage-state orchestrator, and AI-assisted
  drafting remain unimplemented. The geometry-plan adapter is scoped to the
  existing structured character profile and recipe.
- **Reference and image tools:** Blender calibration records source metadata,
  measurements, bounds, cross-sections, and rig landmarks. The front-image
  reader extracts a silhouette with local pixel operations and fits width by
  height; it does not infer unseen depth or surface details. The first-pass
  `inspect_character_source.py` intake records hash-pinned geometry/rig
  inventories and writes unknown-by-default observation drafts; unresolved or
  invalid mesh drivers make evaluated geometry summaries explicitly unreliable.
- **Mesh generation and review:** `generate_character_base.py` builds a
  deterministic parametric blockout, semantic body regions, and landmark
  guides. `character_topology.py` analyzes components/boundaries and gates the
  sampled torso-to-shoulder connection. `refresh_character_base_preview.py`,
  `review_character_base.py`, `export_character_markers.py`, and
  `atlas_marker_placement_addon.py` form the preview, human review, and marker
  handoff. Blender can consume a frozen character geometry build plan and
  records its recipe/plan hashes with the candidate. The explicit
  `--allow-blockout` option and sculpt/T-pose review, preview checksum, and
  rig-authoring-only scope prevent an untouched blockout from advancing. This
  gate does not certify production readiness.
- **Recipe-driven geometry slice:** supported body proportions from the
  existing character recipe now flow through a checksum-bound plan into
  Blender. This does not execute the full cross-category model-recipe schema;
  the builder still emits a low-detail blockout and no target-matching Stone
  Troll mesh has been accepted.
- **Geometry acceptance:** Current review tooling requires explicit sculpt and
  T-pose attestations, a passing sampled shoulder-connectivity check, and an
  unchanged preview hash. It does not yet measure the full geometry acceptance
  checklist; complete visual/anatomical review remains human-led.
- **Texture, landmark, rig, and animation stages:** Existing marker guides and
  manual marker-placement UI are a handoff foundation. Texture recipe/build,
  assisted marker placement, a Stone Troll skeleton/weight generator, and its
  animation authoring/approval stages are not implemented. The former raw
  Mixamo clips were removed during the rights audit; no character animations are
  currently registered.
- **Rig and base assets:** No character GLB, rig, or animation clips are
  currently registered. The previous female model, model-derived humanoid rig,
  vest, and raw Mixamo FBXs were removed because their source rights did not
  support retaining those files in the public project repository.
- **Clothing and runtime assets:** Clothing preparation code remains, but its
  former base mesh and body-region map were removed. It is not a usable workflow
  until a licensed replacement mesh and rig pass review. The asset validator
  checks registered paths and checksums, plus GLB skinning when a manifest entry
  supplies its skeleton contract.
- **Appearance persistence:** browser controls can save a validated traveler
  appearance profile through the local server into SQLite. With the prior model
  removed, the profile currently has no registered character mesh to affect;
  hair, age, stress, and emotion do not drive appearance.
- **World persistence and analysis:** ontology-validated entities, relationships,
  actions, and provenance events are stored in SQLite. APIs expose authored
  graph edits, knowledge/memory reads, observed-event analytics, a narrow
  deterministic resource-progression simulation, policy evaluation, and
  human-reviewed decisions. Deployment of policy-approved world changes is
  not implemented.

| Area | Status | Notes |
| --- | --- | --- |
| Design profiles | Implemented | Structured JSON; free-form prompts are not parsed by Blender. |
| Character geometry builder | Implemented, limited | Explicit `--allow-blockout` procedural mode plus an opt-in, hash-pinned `.glb`/`.blend` source-seed path with human review attestation and coarse supported warps. Neither path is production-ready. |
| Front-image measurement | Tool implemented, no retained image data | Use only sources with documented rights; a single view cannot infer depth or production surface detail. |
| Licensed Troll calibration | Not retained | Stale calibration tied to an unavailable source was removed; CC-BY Troll Mauler remains an authoring reference only. |
| Base review gate | Implemented, human-led | Requires sculpt and T-pose attestations; approval unlocks rig work only. |
| Stone Troll unrigged geometry-only T-pose base | Not complete | External references are available; neither matches the final design or is accepted as the target mesh. No armature or skinning is required for this first approval; rigging follows later. |
| Recipe compiler | Implemented | Applies authored profile/grammar data; does not learn from a dataset. |
| Character recipe-to-Blender geometry plan | Implemented, limited | Hash-bound plan applies supported recipe body proportions and T-pose to procedural geometry or a separately calibrated and reviewed source mesh; it does not execute the full model-recipe contract. |
| Recipe Studio UI and deterministic text compiler | Implemented prototype | Loopback chat UI handles explicit Stone Troll measurements/toggles, plan compilation, procedural blockout generation, and local GLB preview; source-seeded builds remain CLI-only and adjectives are not mapped automatically. |
| Cross-category model recipe schema | Contract groundwork | Captures build detail and provenance; builder/compiler integration is not implemented. |
| General text-to-recipe authoring | Planned, AI optional | Current prototype only maps explicit values for the Stone Troll; broader vocabulary, templates, ambiguity handling, and editable structured review remain. |
| Geometry-to-texture approval workflow | Planned | Geometry-first order is documented; no general stage-state service or procedural texture builder exists. |
| Marker placement UI and skeleton generation | Planned | Blender add-on supports manual marker edits/exports only; the Mixamo-style visual workflow and marker-driven armature builder are not implemented. |
| AI-assisted landmark proposal | Planned | Suggestions, per-marker confidence, and provenance are not implemented. |
| Stone Troll rig and animation pipeline | Not implemented | No character rig or animation clips are registered; rig generation must follow approved visual markers. |
| Structured observation dataset | Intake prototype | Blender source inspection emits hash-pinned technical dossiers and unknown-by-default draft observations; no reviewed dataset has been collected. |
| Relationship discovery/miner | Planned | Recipe curation can run alongside geometry work; do not claim mined findings until the vocabulary and independent licensed dataset support them. |
| Learned-rule approval and recipe composition | Planned | Candidate findings need evidence and human approval before grammar use. |
| Production-quality model generation | Not implemented | Requires a suitable modeling path and high-detail source/sculpt; do not claim the current blockout is production ready. |
| Shared pipeline for every game model category | Not implemented | Character generation and clothing preparation exist; there is no unified generator for props, buildings, environments, and all assets. |
| Age/stress-driven appearance | Not implemented | No simulation state currently changes hair, materials, morphs, or other visual traits over time. |
| Playable world client | Prototype implemented | Browser world/movement sandbox and appearance data persistence; no character model is currently registered after rights cleanup. |
| World graph and history | Local foundation implemented | SQLite entities/relationships and immutable, provenance-bearing events; loopback development API. |
| Analytics and simulation | Narrow prototype implemented | Event counts and one deterministic recorded-event resource-progression counterfactual. |
| NPC personality, emotion, memory, autonomous behavior | Not implemented | Current NPCs and dialogue are scripted prototypes; no persistent agent mind/state yet. |
| Player/NPC and NPC/NPC relationships | Data foundation only | Ontology relationships and event links exist; evolving social relationship behavior is not implemented. |
| Local and inter-city economy | Not implemented | Existing resource progression is not a market or connected economy. |
| Durable accounts and public multiplayer | Not implemented | Current session assignments are local and ephemeral. |
