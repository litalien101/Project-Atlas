# Project Atlas Change History

## Notes maintenance

Whenever work changes this plan, update the relevant status and decision above,
then add a dated note with the implemented files and verification performed.
Keep notes factual: mark ideas as proposed, planned, implemented, or blocked;
do not describe a planned stage as working software.

### 2026-10-03 — Generated model review gallery

- Added a Recipe Studio gallery that lists previous generated Stone Troll
  candidates, loads each available GLB for orbitable inspection, and displays
  build metadata and review state.
- Added a persistent “kept for reference” review record and a confirmed delete
  action scoped to the selected Recipe Studio build directory. Kept candidates
  remain unapproved and are not registered as runtime assets.
- Updated the Recipe Studio run guide, character-generation workflow, status,
  architecture, task list, and character tools index with the gallery's scope.
- Checked Python and JavaScript syntax and diff formatting; exercised loopback
  health, page, and empty-candidate catalog endpoints. No generated candidate was
  present in this checkout for visual or review-action inspection; no test suite
  was run.

### 2026-10-03 — Generation quality guard

- Added an explicit `--allow-blockout` opt-in and clear default refusal when no
  suitable high-detail source is configured.
- Added a `generation_quality` record and a review acknowledgment required
  before a blockout-derived base can be accepted for rigging.
- Historical note: the Stone Troll calibration was reverted to measurement-only
  and stale generated previews removed. A later rights audit removed the
  unavailable calibration and unverified reference images entirely.
- Procedural output is opt-in and labeled `blockout_only`; acceptance requires
  explicit sculpt and T-pose review, and marker placement/export requires a
  checksum-matched review scoped only to rig work.
- Removed the unsuitable Sketchfab Troll calibration, unlicensed Bing reference
  images, derived measurements, and rejected procedural previews from active
  pending-model folders. Pinned the CC-BY Troll Mauler and CC0 Blender human
  base as references; neither matches the Stone Troll target.
- Generated a recipe-driven `blockout_only` Stone Troll candidate in
  `art/characters/pending_models/stone_troll/`. It still needs visual review
  against rights-cleared design references; generation and the sampled shoulder
  test do not establish that the target mesh has been achieved.
- Checked the profile validator, Python syntax compilation, and diff formatting;
  no full test suite was run.

### 2026-10-03 — Recipe-learning groundwork

- Added the master architecture/decision log and an observation schema for
  independent, rights-traceable character examples.
- Added intake guidance that distinguishes observed presence, explicit absence,
  unknown values, structural relations, and source lineage.
- Recorded recipe relationship mining as deterministic, local, evidence-backed
  candidate discovery that follows model-pipeline stabilization; candidates
  need human approval before entering the authored grammar.
- No dataset or statistical learner was added because there are not yet enough
  independent reviewed observations to support findings.

### 2026-10-03 — Whole-world vision recorded

- Expanded this file to include the current browser/server/world-model
  foundation and distinguish it from the planned living-world systems.
- Recorded the intended persistent NPC model: personality, event-derived
  emotions, bounded memory and beliefs, goals, and evidence-backed relationships
  with players and other NPCs.
- Recorded the intended local-to-regional economy and its inventory, currency,
  production, market, and route constraints, plus the staged roadmap for
  implementation and evaluation.

### 2026-10-03 — Full model-pipeline and evolving-appearance scope

- Expanded the model pipeline vision beyond characters to clothing, equipment,
  props, buildings, environments, resources, and other game models.
- Added a traceable trial/review/update loop so learning comes from documented
  outcomes and does not silently rewrite released content.
- Added state-driven character appearance to the roadmap, including gradual
  age- or prolonged-stress-related greying as a species-specific example.
- Marked shared all-asset generation and dynamic age/stress appearance as not
  implemented so the master file distinguishes vision from current software.

### 2026-10-03 — Project-wide architecture inventory

- Expanded the master file from the character-pipeline roadmap into a project
  architecture covering the implemented browser/server/world foundation, the
  full asset-pipeline goal, NPC agent cycle, and linked market/economy design.
- Separated offline recipe learning, individual NPC adaptation, and creator-led
  system improvement into distinct loops with separate evidence and controls.
- Added a system map and links to the detailed source specifications so this
  file remains the overview rather than replacing their contracts.
- Added the master-file update rule to `AGENTS.md` and linked the overview from
  the project `README.md`.
- Validated the Stone Troll profile, Python syntax, observation JSON Schema,
  and diff formatting. No full test suite was run.

### 2026-10-03 — Technical model-recipe contract

- Added `atlas-model-recipe-v1.schema.json` to describe detailed, reproducible
  build inputs across character, creature, clothing, equipment, prop, building,
  environment, and resource categories.
- Specified units and coordinate frames, dimensions and landmarks, weighted
  recipe parameters with evidence/confidence, geometry and topology settings,
  UV policy and material assignments, component transforms/relationships, PBR
  materials and texture metadata, skeleton/rest-pose and skin-weight
  references, animation clip requirements, state-driven variants,
  collision shapes, LODs, performance budgets, rights/provenance, QA evidence,
  and output hashes.
- Distinguished recipe influence weights from per-vertex skinning weights;
  mesh skin data stays in the model or a hashed sidecar referenced by recipe.
- Updated this architecture to state that the full schema is not yet consumed
  by the existing character compiler or Blender builder.
- Validated schema structure and documentation links; no full test suite was
  run.

### 2026-10-03 — Phase A safeguards and mesh-first acceptance

- Tightened base acceptance to fail closed when the quality tier, T-pose,
  sculpt attestation, connected shoulder core, or explicit non-production state
  is missing. Marker editing/export now requires the checksum-matched
  rig-authoring-only acceptance record.
- Defined the first model milestone as geometry-only: a complete design-matched
  T-pose mesh. Textures, skin detail, materials, and runtime release are later
  stages and do not gate the mesh milestone.
- Downloaded and recorded the CC-BY Troll Mauler source and Blender Studio's
  CC0 Human Base Meshes bundle for local reference. Neither was promoted to the
  Stone Troll asset because each needs design-specific sculpting and T-pose
  review. Large binaries remain in an ignored cache and can be fetched again
  with the pinned downloader.
- The Phase A safeguards are in place, but the target Stone Troll mesh is still
  pending. No finished or production-ready model is claimed.
- Checked pinned file hashes, Python syntax, schema/profile validity, and diff
  formatting; no full test suite was run.

### 2026-10-03 — Staged AI-assisted character authoring design

- Recorded the intended path from a creator's text/images through an AI-proposed
  structured recipe, deterministic validation/build planning, Blender geometry,
  creator mesh approval, texture/material approval, landmark review,
  skeleton/skinning, deformation review, animation, and runtime release.
- Defined downstream artifacts as versioned children of approved inputs; edits
  invalidate dependent approvals. AI may propose recipes or landmark positions
  with evidence/confidence, but deterministic checks and creator approvals
  control stage transitions.
- Set the first success target to a design-matched, connected geometry-only
  Stone Troll in the canonical T-pose. Texturing is intentionally the next
  stage, after creator approval of the mesh.
- Documented that “perfect” is an aspiration translated into visible review
  criteria and structural checks, not an automated pass/fail claim. The current
  checks still cover only shoulder connectivity and provenance-bound review;
  full geometry review remains human-led.
- Reordered the character-generation guide to put texture approval before
  landmark placement, matching the intended workflow. Existing tools do not
  yet enforce the complete stage machine or provide AI recipe/marker services.
- Verified Python syntax, diff formatting, and SHA-256 hashes for the pinned
  reference downloads. No test suite was run.

### 2026-10-03 — Rights audit and asset cleanup

- Removed the female runtime/source model and its textures, underwear archive,
  model-derived rig and body-region records, pending Wayfarer vest, and vest
  workspace because the underlying reuse rights were undocumented.
- Removed the two Bing Image Creator reference images, derived silhouette
  measurements, and stale Troll calibration/comparison records whose source was
  unavailable or whose reuse rights were not verifiable for this project.
- Removed the female-base runtime manifest entry, six raw Mixamo FBX clips, and
  disabled character-model loading in the browser. No character mesh or
  animation clips are registered pending rights-cleared replacements.
- Kept the CC-BY Troll Mauler and CC0 Blender human-base references with their
  pinned checksums and license records. They remain references only.
- Updated the asset validator to check registered paths/checksums and GLB
  skinning when a manifest entry declares its skeleton contract. Updated status
  and clothing documentation to identify base-dependent tools as unusable.
- No measurements from the removed image are retained. Recipe evidence
  collection remains an active parallel task and must use rights-cleared,
  independent examples; the authored Stone Troll profile is a target recipe,
  not learned evidence.

### 2026-10-03 — Marker-driven skeleton workflow planned

- Specified a Mixamo-style multi-view UI where creators place, adjust, and
  approve visible joint markers on an accepted character mesh.
- Specified deterministic Blender armature generation from the approved marker
  artifact and a versioned skeleton template, followed by separate skinning,
  deformation, and rig-approval checks.
- This is design only: the existing add-on supports manual marker editing and
  export; the dedicated UI and skeleton generator are not implemented.

### 2026-10-03 — Initial mesh is explicitly unrigged

- Clarified that the first accepted T-pose geometry is an unrigged, unskinned
  mesh. It requires no armature, bones, weights, or animation to pass mesh
  review; those stages follow the later visual-marker workflow.

### 2026-10-03 — Recipe Studio and deterministic geometry slice

- Added `compile_character_geometry_plan.py` to validate a compiled character
  recipe against its source profile, freeze input snapshots and tool/schema
  hashes, and declare the canonical T-pose and no-rig requirement.
- Connected the Blender blockout generator to the frozen plan. The plan's
  supported body values now drive geometry and its recipe/build-plan snapshots
  are recorded with the candidate. It still creates only a low-detail blockout.
- Added a loopback-only chat-style Recipe Studio. Its deterministic text
  compiler handles explicit supported Stone Troll values and feature toggles;
  it preserves prose without guessing proportions. The UI compiles a plan,
  launches Blender for a candidate, and provides a local orbitable GLB preview.
  Each UI build attempt receives a unique trial directory rather than
  overwriting an earlier candidate.
- Added the seed Stone Troll character recipe, local draft-state ignore rule,
  detailed `to_do.md`, and run instructions in the README and generation guide.
- Ran the recipe compiler, geometry-plan compiler, and Blender builder to create
  a review-only candidate. Started the local UI and confirmed its health/page
  responses and explicit-value prompt mapping. No AI service or full test suite
  was used. Target-mesh quality and visual-review gates remain open.

### 2026-10-03 — First-pass source observation intake

- Added a Blender intake command for `.blend`, `.glb`, and `.gltf` sources. It
  records source hashes, scene objects, transforms, mesh/topology/material
  details, rig/actions, driver validity and target binding, and optional
  whole-mesh normalized shape summaries. Invalid or unbound drivers mark
  evaluated geometry as unreliable. Shape measurements use virtual uniform
  height-to-1 normalization; source meshes and transforms remain unchanged.
- Added a versioned anatomy-region vocabulary, four observation states, a
  source-inspection schema, an observation draft schema extension for dossier
  hashes, and a validator for vocabulary/state and human-review metadata.
- Generated records keep semantic labels unknown and rights at
  `review_required`; no source has been promoted and no learning/mining is
  enabled. Updated README, generation guide, observation workflow, and roadmap.
- Verification performed: documentation/code review and JSON schema checks,
  plus a Blender Studio library intake run (382 mesh datablocks; schema-valid
  dossier and draft). No full test suite or model quality review was run.

### 2026-10-03 — Intended player experience and core loop

- Recorded the intended experience as inhabiting a persistent place, learning
  through exploration and relationships, making consequential choices, and
  observing explainable world responses.
- Added a recurring loop from discovering a need or opportunity through
  investigation, action, server-validated consequences, and a new goal.
- Marked progression and reward mechanics as design questions for playtesting;
  this is not a claim that the current prototype implements the loop.

### 2026-10-03 — Reviewed source-mesh adaptation path

- Added an opt-in geometry-seed mode for exact calibrated `.glb` and `.blend`
  mesh objects. The build plan pins source and calibration hashes and freezes
  the rights, topology, and design-fit review attestation.
- The Blender builder now imports the selected mesh, applies supported coarse
  proportion warps, uses source joint bones for arm posing where available,
  and retains source materials while recording provenance. It does not
  retopologize, and features/material controls remain limited.
- Updated the profile contract, calibration guidance, pipeline specification,
  source audit, and per-file TODO audit. The Recipe Studio UI still launches
  only the procedural route. No catalogued source has been approved as a
  Stone Troll seed, and no accepted runtime character was created.
- Verification: inspected the changed implementation and documentation for
  consistency. No tests were run.

### 2026-10-03 — Split project master documentation

- Replaced the monolithic `MASTER_FILE.md` with a concise documentation index
  and explicit ownership/update rules.
- Moved its vision and player experience, architecture, implementation status,
  roadmap, decision log, and dated history into focused documents, preserving
  the prior content.
- Updated contributor guidance, the project README, the character TODO, and
  audit references to point to the new document owners.
- Verification: checked local Markdown links and diff formatting. No tests were
  run.

### 2026-10-03 — Humanoid source technical screening

- Extended the Blender humanoid intake to emit a separate screening report
  alongside the hash-pinned technical dossier and unknown-by-default
  observation draft. Added a versioned report schema with stable reason codes,
  severity, and structured evidence values.
- Kept the first profile limited to measurable technical checks. It does not
  infer visual quality, anatomy, archetype fit, source lineage, or rights, and
  it never approves learning, geometry-seed, or runtime eligibility.
- Added a documented acquisition-to-runtime lifecycle and clarified that
  intake drafts belong in ignored local working data until human review.
- Marked source-dependent build scripts as retired so the active tool surface
  is clear, corrected stale audit findings and documentation conflicts, and
  retained unresolved gameplay-integrity issues on the roadmap.
- Verified the intake on the Blender Studio realistic male source: it produced
  `technically_promising` with no reported topology flags, while rights and
  learning/runtime eligibility remained unapproved. Validated the dossier,
  screening report, and observation draft against their schemas and ran the
  observation validator. A targeted Recipe Studio endpoint exercise also
  confirmed two builds receive separate directories and previews (HTTP 200).
  Checked Python syntax and diff formatting; no full test suite was run.
- Follow-up: centralized the screening status, severity, and outcome constants;
  added a severity-count summary and accepted both screening tool versions in
  the v1 report schema. The existing per-check details remain authoritative.

### 2026-10-03 — Character CLI consolidation deferred

- Recorded a future usability task to consider one `atlas character` command
  surface after the stage contracts and workflows stabilize.
- Deferred a wrapper class or CLI now: the existing tools are still evolving,
  and a premature facade would create another interface to maintain without
  removing the underlying commands.

### 2026-10-03 — Workspace documentation consistency audit

- Clarified document ownership and workspace boundaries in the workspace map,
  Project Atlas index, and Reference Assets indexes. The source-model library
  and Reference Assets are outside this Git repository; their inventories do
  not grant runtime or learning approval.
- Corrected the dated source-model audit to reflect the downloaded but still
  unpromoted Female Low-Poly candidate and the current technical screening
  report. Updated engineering audit entries to reflect verified Recipe Studio
  output isolation without claiming immutable storage, and marked retired
  source-dependent tools accordingly. Audit recommendations now distinguish
  implemented technical triage from remaining visual, archetype, and lineage
  review.
- Marked supplementary Atlas planning and product-vision documents as
  aspirational reference material, clarified that MakeHuman GLB exports are
  not active runtime registrations, normalized the product-vision index to
  `README.md`, and removed copied UI debris from that long-form reference.
- Verified 93 Markdown/text documents for broken relative links (none found),
  parsed all 23 JSON documents and validated all 9 JSON Schema contracts,
  parsed all 19 YAML documents, and reconciled source-catalog counts. Checked
  diff formatting; no application tests were run.
