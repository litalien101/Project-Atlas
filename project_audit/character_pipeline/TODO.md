# Character, Model, and Recipe Pipeline TODOs

Scope: authored character tools, related contracts and records, and the Recipe
Studio handoff. The current pipeline is deterministic and local. It is **not**
a general text-to-3D generator: it parses constrained inputs and produces a
candidate blockout or, with explicit review, a source-seeded draft. The
intended target mesh has not passed review.

The existing root [`to_do.md`](../../to_do.md) is preserved and remains the
active, deeper character-pipeline roadmap. This report is a per-file audit
companion; consolidate status updates rather than maintaining conflicting
duplicate task state.

## First-mesh blocker and stage-gated priorities

- **First-mesh blocker — No accepted Stone Troll mesh.** The builder can now
  generate either blockout geometry or a hash-pinned, reviewed source-seeded
  draft; no documented source is approved as the target geometry. Keep both
  output statuses visible and use the intake route only after an explicit
  human review.
  **Accept when:** a qualified reviewer approves a revision-bound mesh for
  geometry only, supported by complete anatomy/silhouette review and QA
  evidence. Texture, rig, animation, and runtime release remain separate gates.
- **Conditional gate for third-party inputs — Record source rights before reference
  measurement or observation intake.** Calibration and image measurement can
  currently record measurements without a reviewed rights record. Require
  source metadata and a human rights attestation; software can validate
  evidence presence but cannot certify legal interpretation. This does not
  block recipe authoring from original user-authored text.
  **Accept when:** each external source has origin, license/allowed-use scope,
  attribution, and checksum; analysis, derivative, dataset, and redistribution
  permissions remain distinct; unknown/incompatible rights block dataset
  promotion and redistribution.
- **Resolved finding — Isolate candidate artifacts.** Current Recipe Studio
  code assigns a UUID build ID, writes each build under a distinct directory,
  and constructs the preview endpoint from both draft and build IDs. The old
  shared-output claim is stale. Path isolation does not prevent manual edits.
- **P1 before marker editing/export — Verify marker source identity.** Marker
  export checks a preview hash but does not verify that the supplied Blender
  file is the reviewed source. This is a necessary downstream gate, not a
  prerequisite for the first geometry candidate.
  **Accept when:** Blender file hash, preview hash, candidate ID, and approved
  mesh revision match the review record; mismatch blocks export.
- **Incremental — Make the geometry contract honest and executable.** Current geometry
  recipe/plan only drives supported proportions in a blockout. The broader
  cross-category model recipe has no executing builder.
  **Accept when:** unsupported fields are explicitly preserved-only/planned;
  accepted build artifacts have exact input/tool hashes and stage-specific
  validation.
- **Defer porting stale downstream tools.** Several scripts require the
  removed female base and rig; clothing, skeleton/weights, texture, and
  animation stages are not complete. For the first geometry milestone, label
  stale paths as retired/paused so they cannot be mistaken for runnable tools;
  port them only when those downstream stages are scheduled.
  **Accept when:** current workflow documentation does not direct creators to
  stale tools, and future downstream work targets a reviewed replacement
  contract.

## Tools — `tools/characters/*.py`

- [`atlas_marker_placement_addon.py`](../../tools/characters/atlas_marker_placement_addon.py)
  — Keep manual placement gated. Verify the active Blender file hash against
  the reviewed source before allowing edits.
- [`build_atlas_female_base_v1.py`](../../tools/characters/build_atlas_female_base_v1.py)
  — Retire clearly or port. It expects removed female-base and underwear
  inputs; do not present it as runnable current workflow.
- [`build_atlas_humanoid_v1.py`](../../tools/characters/build_atlas_humanoid_v1.py)
  — Retire clearly or port. It depends on the removed female runtime GLB as rig
  source.
- [`build_body_region_schema.py`](../../tools/characters/build_body_region_schema.py)
  — Retire clearly or port. It depends on removed base, rig, and region
  artifacts.
- [`calibrate_character_reference.py`](../../tools/characters/calibrate_character_reference.py)
  — Conditional third-party-input gate: require and retain source URL,
  rights/allowed-use evidence, attribution, and lineage before measuring an
  external reference; do not block measurements of user-authored assets solely
  for lack of third-party license metadata.
- [`character_design_profile.py`](../../tools/characters/character_design_profile.py)
  — Done: distinguish measurement-only `review_only` calibration from the
  explicitly attested `geometry_seed` mode; validate the review fields.
- [`character_image_reference.py`](../../tools/characters/character_image_reference.py)
  — Conditional third-party-input gate: require source/rights metadata before
  measuring an external image and retain it with the measurement artifact.
- [`character_quality.py`](../../tools/characters/character_quality.py) —
  Keep rig-candidate status distinct from geometry or production approval. No
  additional specific defect found.
- [`character_topology.py`](../../tools/characters/character_topology.py) —
  Extend partial sampled shoulder-connectivity checks to recipe-required
  regions and wrist/hand joins; define applicable boundary/manifold policy.
- [`compare_character_calibrations.py`](../../tools/characters/compare_character_calibrations.py)
  — No retained calibration is available to compare. Use only after
  rights-cleared records exist; no additional specific defect found.
- [`compile_character_geometry_plan.py`](../../tools/characters/compile_character_geometry_plan.py)
  — Supports hash-pinned source geometry inputs and freezes calibration and
  review evidence. Remaining: preserve and verify the grammar artifact/hash
  used to produce the recipe; distinguish source-seed and blockout limits.
- [`compile_character_recipe.py`](../../tools/characters/compile_character_recipe.py)
  — Validate the full grammar against its schema; represent draft relationships
  as draft, not just draft archetype rules.
- [`compile_model_build_plan.py`](../../tools/characters/compile_model_build_plan.py)
  — Candidate planner only. Mark executable versus preserved-only plan fields
  and record whether file checks were skipped; no builder consumes the full
  contract.
- [`deterministic_recipe_compiler.py`](../../tools/characters/deterministic_recipe_compiler.py)
  — Detect conflicting explicit values and preserve per-field origin. Do not
  infer anatomy from adjectives or imply general prompt understanding.
- [`download_reference_model.py`](../../tools/characters/download_reference_model.py)
  — No specific defect found. Preserve pinned checksum/license behavior and
  label downloads as authoring references, not approved geometry.
- [`export_character_markers.py`](../../tools/characters/export_character_markers.py)
  — Before marker export: verify the supplied Blender file against the
  reviewed source hash and validate exported markers against the landmark
  schema. This is downstream of first-mesh approval.
- [`generate_character_base.py`](../../tools/characters/generate_character_base.py)
  — Keep blockout label; target mesh is missing. Add reviewed authored/sculpted
  intake and enforce reference rights. Recipe Studio outputs are isolated by
  draft/build IDs, but files are not protected against later manual mutation;
  do not call them immutable.
- [`inspect_character_source.py`](../../tools/characters/inspect_character_source.py)
  — First-pass technical intake and humanoid screening are implemented for
  `.blend`, `.glb`, and `.gltf`. They emit a hash-pinned dossier, technical
  screening report, and unknown-by-default observation draft; they do not
  verify license claims, judge visual quality, or infer anatomy. Remaining
  work is archetype-specific visual review assistance and lineage review.
- [`generate_wayfarer_vest_seed.py`](../../tools/characters/generate_wayfarer_vest_seed.py)
  — **Retired in the current workflow.** It remains as a historical reference
  and refuses direct execution because it depends on removed female-base and
  region files. Port only against a reviewed replacement base and contract.
- [`model_recipe_pipeline.py`](../../tools/characters/model_recipe_pipeline.py)
  — Contract validation/planning only. Tighten semantic validation of
  constraints, ranges, coordinate frames, rights, and release evidence;
  unknown rights must not satisfy release.
- [`prepare_clothing_asset.py`](../../tools/characters/prepare_clothing_asset.py)
  — Paused/stale: hard-coded to retired body, rig, and region schema. Port only
  after a reviewed replacement base/rig exists.
- [`recipe_studio_server.py`](../../tools/characters/recipe_studio_server.py)
  — UUID draft/build paths and preview lookup agree in the current code; the
  earlier shared-output overwrite finding is resolved. If changed, verify that
  response IDs, candidate record, and preview URL identify the same build.
- [`refresh_character_base_preview.py`](../../tools/characters/refresh_character_base_preview.py)
  — No specific invalidation defect found. Preserve review invalidation on
  refresh and retain earlier review outcomes as history rather than
  overwriting them.
- [`register_clothing_asset.py`](../../tools/characters/register_clothing_asset.py)
  — Paused/stale: tied to `ATLAS_HUMANOID_V1`. Port only with a reviewed
  replacement rig and matching asset contract.
- [`review_character_base.py`](../../tools/characters/review_character_base.py)
  — Preserve the limited human gate; attestations are not automated proof of
  sculpt quality. Make review history append-only and candidate-revision-bound.
- [`validate_character_assets.py`](../../tools/characters/validate_character_assets.py)
  — Runtime validator, not candidate QA. Keep path/checksum and declared
  skeleton checks; add release/provenance gates when replacement assets exist.
- [`validate_character_design_profile.py`](../../tools/characters/validate_character_design_profile.py)
  — No additional specific defect found. Keep creator-profile validation
  distinct from recipe, observation, and runtime-asset validation.
- [`validate_model_recipe.py`](../../tools/characters/validate_model_recipe.py)
  — Strengthen semantic checks in the shared pipeline; schema-valid does not
  imply executable or release-approved.

## Character/model specifications

- [`atlas-character-design-profile-v1.schema.json`](../../specs/atlas-character-design-profile-v1.schema.json)
  — Done: separate `review_only` from `geometry_seed` and require a structured
  human geometry-seed review attestation. This records review; it cannot
  determine whether license interpretation or visual quality is correct.
- [`atlas-character-generation.md`](../../specs/atlas-character-generation.md)
  — Done: distinguish recipe fields consumed by the builder from preserved
  guidance, document both geometry paths and their limits, and clarify that
  review flags are human attestations rather than automated proof.
- [`atlas-character-grammar-v1.schema.json`](../../specs/atlas-character-grammar-v1.schema.json)
  — Tighten typed evidence/relationship validation; do not promote draft rules
  without reviewed independent examples.
- [`atlas-character-observation-v1.schema.json`](../../specs/atlas-character-observation-v1.schema.json)
  — Draft contract plus a first-pass intake/validator; no reviewed
  dataset/miner exists. Require rights-cleared, reviewed, independent-source
  evidence for eligibility.
- [`atlas-character-source-inspection-v1.schema.json`](../../specs/atlas-character-source-inspection-v1.schema.json)
  and [`atlas-character-observation-vocabulary-v1.json`](../../specs/atlas-character-observation-vocabulary-v1.json)
  — New first-pass dossier and anatomy-region contracts. Expand only when
  review or reconstruction comparisons show which missing data matters.
- [`atlas-character-profile-v1.schema.json`](../../specs/atlas-character-profile-v1.schema.json)
  — Legacy runtime/save contract. Keep separate from creator profiles and
  version/migrate female-base-specific fields before new variants connect.
- [`atlas-character-recipe-v1.schema.json`](../../specs/atlas-character-recipe-v1.schema.json)
  — Add typed body fields, relationships, pose/evidence semantics, and
  cross-reference validation.
- [`atlas-character-technical-spec-v1.md`](../../specs/atlas-character-technical-spec-v1.md)
  — No specific defect found. It accurately records no registered model/rig
  and future GLB, skeleton, provenance, and review needs; update when contract
  changes.
- [`atlas-clothing-authoring.md`](../../specs/atlas-clothing-authoring.md)
  — Accurately paused. Resume only against a reviewed replacement base/rig and
  keep fit, deformation, provenance, and release review distinct.
- [`atlas-model-recipe-v1.schema.json`](../../specs/atlas-model-recipe-v1.schema.json)
  — Cross-category contract only; builder integration and semantic/release
  validation remain TODO.
- [`atlas-rig-landmarks-v1.schema.json`](../../specs/atlas-rig-landmarks-v1.schema.json)
  — Handoff contract only; bind to exact reviewed source. Consider fingertip
  anchors and marker-level review/confidence before rig generation.
- [`asset-provenance.md`](../../specs/asset-provenance.md) — Align reference
  intake/candidate records with redistribution gates; analysis permission is
  not runtime clearance.

## Authored character records and README files

- [`stone_troll.json`](../../art/characters/profiles/stone_troll.json) —
  Authored design input, not evidence. No specific record defect found; it
  correctly records unfinished blockout and absent generated actions.
- [`atlas_character_grammar_v1.json`](../../art/characters/grammars/atlas_character_grammar_v1.json)
  — Draft guidance with empty evidence; collect reviewed examples before
  promoting rules.
- [`stone_troll_v1.json`](../../art/characters/recipes/stone_troll_v1.json) —
  Candidate recipe, not learned output. Keep draft status and profile/grammar
  hashes synchronized; no independent evidence is recorded.
- [`recipes/README.md`](../../art/characters/recipes/README.md) — No specific
  defect found; correctly distinguishes recipes from observations.
- [`recipe_observations/README.md`](../../art/characters/recipe_observations/README.md)
  — Documents first-pass intake and its limits; there is still no approved
  dataset or miner and derived copies remain non-independent evidence.
- [`references/README.md`](../../art/characters/references/README.md) — No
  specific defect found; correctly separates authored design from licensed
  observations and requires source rights/lineage.
- [`sources/README.md`](../../art/characters/sources/README.md) — Keep license,
  attribution, checksum, and limitations. The cited sources are not accepted
  Stone Troll geometry.

## Recipe Studio UI and handoff

The local [`recipe_studio/`](../../tools/characters/recipe_studio/) interface
is limited to deterministic Stone Troll authoring. Keep its “no AI” and
blockout-only messaging accurate. Build and preview actions use
revision-specific IDs; never expose a successful candidate response when
Blender failed or the returned record cannot be verified.

## Planned downstream stages

- [ ] Add texture/material authoring and independent approval tied to the
  approved mesh hash; capture UV/channel, resolution, colorspace, seed,
  parameters, rights, and checksums.
- [ ] Version the marker/skeleton contract; build a deterministic skeleton
  only after marker review; separate skin weights and deformation evaluation.
- [ ] Review representative shoulder, elbow, wrist/finger, hip, and knee
  deformations; marker approval must not imply rig approval.
- [ ] Add licensed/authored animation only after rig approval, with exact
  clip/retargeter/rig hashes, root-motion policy, action coverage, and distinct
  review.
- [ ] Resume clothing only against approved replacement base/rig, or retire
  scripts from runnable workflows. Reject stale body-region hashes and test
  fit, deformation, clipping, provenance, license, and runtime budgets.
- [ ] Build observation mining only from a reviewed, rights-cleared dataset.
  Report source counts, exclusions, uncertainty, lineage, and hashes; require
  human approval before learned grammar changes.
