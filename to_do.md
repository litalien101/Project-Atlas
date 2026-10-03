# Project Atlas To Do

This is the actionable work list for the character asset-authoring pipeline.
It complements the documentation set indexed in [`MASTER_FILE.md`](MASTER_FILE.md):
see [`ARCHITECTURE.md`](ARCHITECTURE.md) for system design and
[`STATUS.md`](STATUS.md) for implementation state. Check an item only when the
code or asset exists and its stated review gate has been met. A generated
candidate is not an approved asset.

## P0 — Produce and review the first Stone Troll geometry candidate

- [x] Keep the first deliverable scoped to a complete T-pose geometry mesh.
  Textures, fine surface detail, armature, bones, skin weights, and animation
  are later stages.
- [x] Require an explicit blockout opt-in and mark procedural output as
  `blockout_only` and not production-ready.
- [x] Add a geometry build-plan compiler for the existing validated character
  profile and compiled character recipe. It records exact input snapshots and
  SHA-256 hashes, restricts the pose to `t_pose_fingers_spread`, and records
  that rigging is not required for this build.
- [x] Make Blender consume the frozen geometry build plan, reject changed or
  missing inputs/tool revisions, and retain the recipe and plan beside the
  candidate outputs.
- [x] Add a loopback-only recipe authoring UI with a polished chat-style brief
  composer, explicit parse feedback, recipe summary, plan compile, Blender
  candidate build, and an orbitable local GLB preview.
- [x] Keep the first text compiler deterministic and narrow: parse explicit
  supported measurements and feature toggles; preserve qualitative prose as
  source text; require the creator to acknowledge that unparsed language does
  not change geometry.
- [x] Generate a Stone Troll blockout candidate from the recipe-driven plan in
  Blender. The pending `.blend`, GLB, recipe, build plan, region data, and
  candidate record are under `art/characters/pending_models/stone_troll/`.
- [ ] Visually inspect the saved `.blend` and GLB preview; generation success
  and a passing narrow topology check do not count as design approval.
- [ ] Compare front, side, and back silhouettes with rights-cleared design
  references; source/reference images must not be retained or used without
  documented rights.
- [ ] Review proportions, head/face features, shoulder and armpit transitions,
  complete arms, wrist-to-hand continuity, fingers/thumbs, legs/feet, normals,
  boundaries, and unexplained disconnected or intersecting geometry.
- [ ] Record a concrete accept/reject decision and rationale against the exact
  preview hash. Rejecting the candidate should create a new recipe/build
  revision, not overwrite the previous trial evidence.
- [ ] Keep the accepted result scoped to geometry review only. Do not call the
  procedural blockout production-quality or runtime-ready.

## P1 — Make geometry recipes control the Blender build reliably

- [x] Validate the character recipe against `atlas-character-recipe-v1` and
  confirm its profile hash, character ID, supported builder, body fields, and
  canonical T-pose before compiling a build plan.
- [x] Apply recipe body proportions to the effective Blender build profile;
  retain the original profile separately for provenance.
- [ ] Add explicit, versioned recipe fields for geometry controls that are
  currently implicit in generator code, including body resolution, surface
  smoothing, feature geometry, and permitted connected-region expectations.
- [ ] Make the builder reject unknown geometry instructions rather than
  silently ignoring them.
- [ ] Expand structural QA beyond the sampled shoulder-core gate: report
  component sizes, boundary and non-manifold edges, duplicate/degenerate
  geometry, normals, dimensions, and expected region connections with clear
  severity and rationale.
- [ ] Keep structural checks separate from visual judgment. Automated results
  must not claim that anatomy, silhouette, or design fidelity is approved.
- [ ] Add a repeatable preview bundle with front/side/back and detail views,
  scale ruler, region colors, landmarks, and QA summary for each revision.
- [ ] Version the geometry recipe/build-plan contract before adding controls
  that change existing recipe behavior.

## P1 — Expand deterministic text-to-recipe authoring

- [x] Build the first `Recipe Studio` UI, served locally at `127.0.0.1`, with no
  remote model or external service call.
- [x] Show parsed values, applied source text, draft status, scope limits, and
  what remains for later stages before allowing plan compilation.
- [x] Save drafts, compiled character recipes, and build plans beneath ignored
  local `data/recipe_studio/` state; add an explicit button to run the Blender
  blockout builder and inspect its local preview. UI build attempts receive
  unique trial directories so a later attempt does not overwrite an earlier
  candidate.
- [x] Add a generated-candidate gallery to browse and preview prior Recipe
  Studio builds, mark candidates kept for reference, or delete one selected
  generated build with a scoped server-side path check and confirmation.
- [ ] Add versioned phrase/alias tables and fixture examples for the supported
  deterministic vocabulary.
- [ ] Add explicit template selection only after each archetype has its own
  validated profile and builder support; the first UI must not silently turn a
  Stone Troll into another species.
- [ ] Add clear, field-specific questions for ambiguous values and conflicting
  requirements instead of inferring proportions from adjectives.
- [ ] Add UI controls to review/edit supported fields and source assumptions
  before compiling; preserve the original prompt unchanged.
- [ ] Expand prompt mapping to palette/material and later-stage recipe fields
  only when corresponding validators and builders exist.
- [ ] Consider an AI adapter only for genuinely ambiguous descriptions; keep it
  optional, label its proposals, and require deterministic validation and user
  review before any proposed value reaches a recipe.

## P1 — Collect rights-cleared observations and mesh QA evidence

- [ ] Maintain a source register with exact title, creator, original URL,
  license/terms, acquisition date, source checksum, permitted uses, and
  derivative/redistribution limits.
- [ ] Evaluate the retained CC-BY Troll Mauler and CC0 Blender human-base
  sources as references only; document whether each is useful for a specific
  measurement or anatomy region. Do not treat either as a Stone Troll result.
- [x] Add an intake command that inspects a GLB/GLTF/Blend source and
  emits a draft observation and mesh QA dossier without claiming license
  validity or design approval.
- [x] Emit a hash-pinned, explainable humanoid technical-screening report with
  `technical_concern`, `needs_human_review`, and `technically_promising`
  outcomes. Report measurable mesh/bounds/topology/driver findings, use no
  polygon-count quality threshold, and keep rights, learning, and runtime
  eligibility unapproved.
- [ ] Add visual, archetype-specific screening assistance for pose, anatomy
  visibility, clothing/occlusion, and fit to a stated observation question.
  Keep outputs as reviewer prompts; do not infer semantic labels or approve
  quality automatically.
- [ ] Add source-lineage review support that flags possible duplicate variants
  or derivatives from catalog metadata and hashes. A reviewer must resolve
  lineage; byte hashes alone do not establish independent authorship.
- [x] Report source mesh counts, dimensions, transforms, connected components,
  boundary/non-manifold edges, normals, material slots, armature presence, and
  available mesh attributes in a deterministic machine-readable record.
- [x] Normalize focus-mesh shape summaries virtually to one unit of world-Z
  height, while retaining the unchanged source hash, original bounds, and unit
  metadata; require a human to review pose/orientation assumptions.
- [x] Define a versioned semantic vocabulary for head, neck, torso, shoulder,
  upper arm, forearm, hand, pelvis, thigh, calf, and foot regions.
- [x] Support explicit `present`, `absent`, `unknown`, and `not_applicable`
  observation states; do not infer unseen anatomy from a front view.
- [x] Create a draft observation with unknown semantic-region labels; keep it
  separate from the source model and from the build recipe.
- [x] Add schema and semantic validation for observation drafts and require a
  named reviewer, UTC timestamp, and rationale before a record can claim
  reviewed status.
- [ ] Build an extraction-to-reproduction evaluation loop: record which
  reviewed source measurements/features map to recipe or builder controls,
  compare a generated result against the exact source/design target, and log
  mismatches before deciding which extractor fields are missing.
- [ ] Refine the vocabulary and extraction fields from those reviewed
  mismatches, with a versioned schema change and a before/after comparison;
  do not add fields solely because they are easy to measure.
- [ ] Define separate vocabularies and reference-dimension policies for
  quadrupeds, dragons, and other non-humanoid archetypes before extracting
  their observations; do not apply humanoid height normalization to them.
- [ ] Require a human reviewer to confirm extracted regions, measurements,
  license evidence, and lineage before an observation is approved.
- [ ] Record relationships between revisions and source assets so edited copies
  do not count as independent examples.
- [ ] Collect a useful set of independent, licensed, reviewed examples before
  reporting statistical anatomy findings. Until then, keep grammar rules marked
  draft or authored guidance and do not claim the system has learned them.

## P2 — Add a creator review and iteration loop

- [ ] Provide a local review screen or Blender workspace that opens a candidate
  with its reference views, recipe values, assumptions, and QA report together.
- [ ] Let reviewers accept, reject, or request changes with a required rationale
  and reviewer identity.
- [ ] Bind every review to the exact mesh, preview, recipe, plan, builder, and
  source hashes.
- [ ] Invalidate downstream approvals when a parent mesh or recipe changes.
- [ ] Store each generated attempt, changed controls, QA results, reviewer
  outcome, and output hashes as a traceable build trial.
- [ ] Add recipe diffs so a reviewer can see which parameter changes were made
  between a rejected and revised candidate.

## P3 — Geometry-approved to texture/material authoring

- [ ] Define a texture-stage recipe that references an approved geometry hash
  and names surface regions, material IDs, shader settings, UV policy, and map
  requirements.
- [ ] Generate or author UVs only after geometry approval; validate UV coverage,
  overlaps, texel density, and distortion for the intended use.
- [ ] Build deterministic procedural material/texture tools for supported
  channels, with fixed seeds and recorded parameters. Do not imply AI texture
  generation exists until a real adapter and review path are implemented.
- [ ] Record texture dimensions, color space, source rights, tool version,
  parameters, and checksums.
- [ ] Review the textured model under documented neutral lighting and from
  multiple views; keep appearance approval separate from geometry approval.
- [ ] Keep edits to approved geometry out of the texture stage; geometry changes
  require a new mesh revision and renewed geometry review.

## P4 — Visual landmark placement and rig generation

- [ ] Build a creator-facing multi-view marker UI with draggable Mixamo-style
  visual anchors for root/pelvis, spine, neck, head, eyes, shoulders, elbows,
  wrists, hand roots/fingertips, hips, knees, ankles, and feet.
- [ ] Let users inspect and adjust each marker in front, side, and other useful
  model views; paired-limb mirroring may provide an editable starting point.
- [ ] Store marker coordinates in a declared model-space frame and bind the
  marker artifact to the exact approved geometry hash.
- [ ] Optionally propose marker positions with deterministic mesh analysis or
  AI assistance; preserve method, confidence, and provenance, and require user
  review of every proposed marker.
- [ ] Add a versioned skeleton template and deterministic Blender armature
  builder that maps approved markers to bone names, hierarchy, orientations,
  rest pose, and joint limits.
- [ ] Generate skin weights as a separate step; validate normalization,
  influence limits, unweighted vertices, and weight transfer provenance.
- [ ] Preview shoulders, elbows, wrists/fingers, hips, and knees through
  repeatable deformation poses.
- [ ] Require a separate rig/deformation review before approving the rig.

## P5 — Animation authoring and retargeting

- [ ] Define the Atlas animation clip contract: action ID, rig hash, clip hash,
  duration, root-motion behavior, source rights, and review state.
- [ ] Choose rights-cleared authored, procedural, or retargeted motion sources;
  do not restore restricted animation files as training or project assets.
- [ ] Create an initial action set from the character brief after the rig passes
  deformation review (idle, walk, run, jump, climb, and other requested actions).
- [ ] Validate contacts, balance, foot sliding, clipping, joint limits,
  deformation, and transitions in Blender and the target runtime.
- [ ] Keep animation approval separate from mesh, texture, and rig approvals.

## P6 — Package and release approved assets

- [ ] Export the approved mesh/rig/material/animation set with declared units,
  coordinate frame, naming, and supported formats.
- [ ] Validate hashes, provenance, license/redistribution status, dimensions,
  mesh/rig compatibility, textures, animation references, and runtime budgets.
- [ ] Register only exact, reviewed output hashes in the runtime asset manifest.
- [ ] Verify that the client loads the registered model and required animations;
  never serve mutable work-in-progress files as production assets.
- [ ] Document rollback and replacement behavior for a released asset revision.

## P7 — Learn from reviewed recipes and trials

- [ ] Normalize recipe and observation fields into versioned trait, anatomy,
  material, and relationship vocabularies.
- [ ] Build a deterministic local miner for co-occurrence and typed relations
  once enough independent approved observations exist.
- [ ] Report support counts, denominators, uncertainty, exclusions, source IDs,
  data hashes, and related-source grouping for every candidate finding.
- [ ] Evaluate findings on held-out sources against simple baselines and retain
  negative evidence and exceptions.
- [ ] Keep mined findings as candidates until a reviewer approves a versioned
  grammar rule.
- [ ] Use approved findings as traceable recipe suggestions; never let learned
  patterns override explicit creator requirements or silently change an
  approved mesh.

## Current implementation boundary

The profile/character-recipe compiler, geometry build-plan adapter, procedural
Blender blockout builder, narrow shoulder-connectivity check, preview refresh,
manual base review, manual marker handoff, and first-pass Blender source intake
tool exist. Intake emits technical summaries and unknown-by-default observation
drafts; it has not produced approved observations or an automated quality
screening report. The full model-recipe
contract is not executed. The current builder remains a low-detail blockout
generator. Deeper semantic extraction and review UX, a reviewed observation
dataset, a target-matching Stone Troll mesh, texture generation, Mixamo-style
marker UI, marker-driven skeleton and
weight generation, animation authoring, and the end-to-end stage state machine
remain unfinished.
