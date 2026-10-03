# Project Atlas — Goal-Aware Priority TODO

This audit spans multiple independent product tracks. Priority labels indicate
risk or stage importance; they are **not** a single serial work queue. For the
current CPU-friendly T-pose mesh objective, use the character track below and
the detailed checklist in [`../to_do.md`](../to_do.md). The confirmed gameplay
integrity fixes can proceed in parallel; they do not block offline model
generation.

## Track A — First useful CPU-friendly character geometry

### A0 — Make the first mesh target measurable

- [ ] Define the target Stone Troll design, scale/units, axes, exact T-pose,
  required visible anatomy, allowed variation, and acceptable front/side/back
  silhouettes. Identify a human-approved reference or manually authored
  exemplar as a comparison oracle, not as a replacement for generator work.
- [ ] Keep the local deterministic compiler and Blender builder. Do not add a
  neural text-to-3D dependency unless a benchmark identifies a concrete
  requirement it meets better than the constrained CPU-first path.
- [ ] Keep text interpretation explicit: preserve original brief, show parsed
  and unparsed phrases and per-field origin, reject or clarify conflicts, and
  require acknowledgement before build. Unsupported prose must not silently
  affect geometry.

### A1 — Preserve candidates and measure the actual CPU path

- [x] Isolate Blender build outputs by UUID and bind each preview request to its
  `draft_id` and `build_id`. Code review confirms separate output directories;
  the previous shared-destination finding is resolved. This is path isolation,
  not protection against manual modification of generated files.
- [x] Targeted local endpoint exercise completed (2026-10-03): two builds
  returned distinct build IDs and output paths; both build-specific preview
  URLs returned their own nonempty GLB with HTTP 200. This verifies endpoint
  binding and path separation, not immutable storage or deterministic geometry.
- [ ] Measure deterministic repeatability, wall-clock time, peak memory, mesh
  counts, and failure behavior on the intended CPU machine. Set performance
  budgets from measurements rather than guessed thresholds.
  **Done when:** repeated builds with identical inputs/tool version produce
  equivalent declared outputs and a recorded benchmark defines the supported
  hardware envelope.

### A2 — Iterate for design fidelity and review

- [ ] Improve the builder toward the measured target; keep metaball output as
  a clearly labelled fast blockout if useful. Add explicit, versioned recipe
  parameters only when the builder executes them.
- [ ] Run cheap structural checks on each build: finite coordinates, pose and
  scale bounds, required region/component connections, normals,
  degenerate faces, and basic boundary/manifold counts.
- [ ] Measure CPU cost before making expensive checks such as self-intersection
  analysis mandatory. Keep them optional until their cost and value are known.
- [ ] Produce repeatable front/side/back and detail previews with scale,
  recipe assumptions, landmarks, and QA results.
- [ ] Record a human accept/reject decision against the exact candidate hash.
  Visual design fidelity is not established by topology checks.
  **Done when:** the complete T-pose form matches the agreed target in all
  review views, passes applicable structural checks, and receives geometry-only
  human approval.

Details: [`character_pipeline/TODO.md`](character_pipeline/TODO.md).

## Track B — Current gameplay integrity (parallel, promptly fix)

- [ ] **Reject forged server action context.** Validate per-action request
  shapes, reject reserved server-only keys, and keep trusted rewind context
  separate from client input. A forged `_attack_origin` was confirmed to
  enable an out-of-range attack.
  **Done when:** the request causes no state/event mutation, valid
  server-resolved rewind still works, and reserved fields are rejected.
- [ ] **Make projection rebuild idempotent.** Replay event-derived state from
  declared clean baselines rather than already-reduced projections.
  **Done when:** repeated rebuilds preserve exact documented inventory,
  health, journal, combat, and tick state.
- [ ] **Apply local origin/host checks to session creation.** This is a small
  relevant safeguard for the existing local browser/server use, independent
  of the offline geometry work.
  **Done when:** rejected cross-origin creation consumes no seat.

Details: [`server/TODO.md`](server/TODO.md).

## Track C — Active user-facing/gameplay behavior

- [ ] Show accurate connection failure and retry status in the browser.
- [ ] Make supported local player count consistent in the spec/server/UI; if
  two-seat play remains an active claim, render the remote traveler.
- [ ] Make appearance controls honest while no character model is registered.
- [ ] Fix focused-control keyboard handling and resolve only the Studio pages
  that are part of the active user workflow. The separate missing
  `web/studio.js` is not a prerequisite for the Recipe Studio geometry path.

Details: [`web/TODO.md`](web/TODO.md).

## Conditional prerequisites and later stages

- [ ] For **third-party references or observation intake**, record source
  origin, license/allowed-use scope, attribution, checksum, and human rights
  attestation. Software validates evidence presence; it does not certify legal
  interpretation. This does not block recipe authoring from original user
  text. Unknown or incompatible rights block observation promotion and
  redistribution.
- [ ] Before marker editing/export, bind the Blender file and preview to the
  reviewed geometry candidate hash. This is a downstream gate, not a
  prerequisite for first-mesh geometry generation.
- [ ] Keep source observations, profiles, recipes, build plans, generated
  candidates, and runtime assets distinct and versioned. Do not build a recipe
  miner until enough independent, reviewed, rights-cleared observations exist.
- [ ] Implement materials, markers, skeleton, weights/deformation, animation,
  clothing, and runtime release only when the prior stage has passed and the
  next stage is in scope. Keep approval scoped to its stage and parent hashes.
- [ ] Reconcile documentation/link/license inconsistencies when editing the
  affected docs; avoid creating policy/schema machinery without an active
  consumer.
- [ ] Treat public accounts/networking, authenticated creator/reviewer roles,
  migration operations, backups, observability, abuse response, rollback, and
  full release gates as deployment prerequisites, not offline mesh-pipeline
  prerequisites.
- [ ] Keep persistent NPC cognition and a connected economy as roadmap work;
  do not describe scripted prototype behavior as those systems.

Details: [`project_contracts/TODO.md`](project_contracts/TODO.md),
[`character_pipeline/TODO.md`](character_pipeline/TODO.md), and
[`server/TODO.md`](server/TODO.md).

## Completion criteria across tracks

- [ ] Every current capability claim in `../STATUS.md` matches implemented
  behavior and evidence.
- [ ] Game actions do not trust client-supplied server-only context, and event
  projection rebuild is deterministic and idempotent.
- [ ] The first-mesh acceptance gate above is satisfied independently of
  rigging, texturing, animation, or runtime release.
- [ ] No asset is represented as approved, rights-cleared, or production-ready
  beyond the evidence and review scope it actually has.
