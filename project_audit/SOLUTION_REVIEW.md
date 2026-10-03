# Are the Audit Solutions the Best Fit for Project Atlas?

## Short answer

The proposed fixes are mostly technically sound and align with the project's
[`../ARCHITECTURE.md`](../ARCHITECTURE.md) and
[`../STATUS.md`](../STATUS.md): deterministic local generation,
separate evidence and recipes, revision-bound review, replayable world state,
and honest capability claims. They are not all equally urgent for your
immediate objective, however. The audit's priority labels combine gameplay
integrity, future release hardening, and the first character-mesh milestone.
Treat them as risk labels, not as one serial work queue.

Your immediate objective, reflected in [`../to_do.md`](../to_do.md), is a
useful text-to-recipe-to-T-pose geometry path that runs locally on CPU and
produces a candidate shaped to the design—not a general-purpose neural
text-to-3D product, not a rigged character, and not merely a successful
Blender export. The present blockout is explicitly not yet that accepted
geometry result.

## Recommended order for your goal

### 1. Keep independent work tracks separate

- **Fix the two confirmed server defects promptly** on the gameplay track:
  forged server-only action context and non-idempotent projection rebuilds.
  These are genuine integrity defects, but neither is a prerequisite for
  building the offline character generator. Complete them before relying on
  the affected gameplay/rebuild behavior or expanding networking.
- **In parallel, prioritize the character milestone below.** Do not hold up
  geometry work for remote-player rendering, mobile controls, public accounts,
  NPC minds, economies, animation, or release operations. Those are separate
  product tracks and later gates.

### 2. Define one measurable geometry target before adding generator features

Write down the Stone Troll reference/brief, scale and axes, exact neutral
T-pose, required visible anatomy, allowed design variation, and what counts as
an acceptable silhouette from front/side/back. A mesh can be watertight and
connected yet still be the wrong troll. Have a human approve a target/reference
or a manually authored gold-standard mesh; use that as a validation oracle,
not as a substitute for the eventual recipe-driven generator.

### 3. Make the current CPU-first path safe and reproducible

- Keep the current local deterministic compiler and Blender builder; do not
  add a neural text-to-3D dependency unless a later benchmark establishes a
  concrete need. It would add model/runtime dependencies without solving
  anatomy or design fidelity automatically.
- Keep prompt parsing constrained to supported fields. Preserve the original
  brief, show parsed/unparsed text and field origins, ask for clarification on
  conflicts, and require acknowledgement before build. Never let an adjective
  silently change geometry.
- Make Blender candidate output immutable per build. The root TODO says UI
  attempts get unique trial directories, while the audit found the build
  server's output path is shared. Preserve the existing draft/trial behavior
  and fix the specific Blender output/preview endpoint path so one build cannot
  replace another build's candidate.
- Record a repeatability and performance baseline on the intended CPU machine:
  identical inputs/tool version produce equivalent geometry and hashes; record
  wall-clock time, peak memory, mesh counts, and build failure. Set numeric
  budgets after measuring the target hardware instead of guessing thresholds.

### 4. Improve the actual geometry, not just the pipeline paperwork

Once the target is fixed, iterate the builder toward it. A practical CPU-first
approach is a bounded parametric generator with reusable anatomy/shape
components and deterministic surface construction, driven only by explicit
recipe fields. The current metaball blockout can remain a fast preview mode; do
not treat more validation around it as a replacement for target-matching
geometry. Use the gold-standard design to compare silhouette and required
features at each revision.

Add QA in tiers:

- Run cheap deterministic checks on every build: finite coordinates, scale and
  pose bounds, component and expected-region connectivity, normals, degenerate
  faces, and basic boundary/manifold counts.
- Run more expensive checks, such as self-intersection diagnostics, as
  optional review checks until their CPU cost is measured.
- Keep visual/design decisions—silhouette, proportions, complete hands and
  feet, and fidelity to the brief—as human review with front/side/back
  evidence. Automated topology results must not imply visual approval.

### 5. Apply rights controls proportionately

The provenance recommendations are important for using third-party models and
images, creating observations, and redistributing assets. They should not
prevent writing a recipe or generating from original user-authored text.
Record source, license, checksum, permitted use, and a human rights
attestation when an external source is involved. The tool can validate that
required fields/evidence exist; it cannot certify that a license interpretation
is legally correct. Unknown or incompatible rights must block redistribution
and use in an approved observation dataset; do not describe them as software-
verified legal clearance.

### 6. Defer later stages until geometry passes

The proposed separation of geometry, materials, markers, rig, weights,
animation, and runtime registration is the right architecture. Implement those
contracts when the geometry stage is accepted and the next stage is actually
being built. In particular, exact `.blend`-to-review hash checks are a
necessary gate before marker placement/export, but should not be mistaken for
progress toward first-mesh shape quality.

Recipe mining should remain deferred until enough independent, reviewed,
rights-cleared observations exist. A seed recipe or a series of generated
variants is not evidence that the system has learned anatomy.

## Assessment by report

| Report | Fit | Recommendation |
|---|---|---|
| [`PRIORITY_TODO.md`](PRIORITY_TODO.md) | Sound tasks, but its single ordering places gameplay integrity and future release controls beside the character milestone. | Use separate gameplay and character tracks; follow the goal-specific order above. Do the two confirmed server integrity fixes promptly, but do not block offline mesh work on them. |
| [`character_pipeline/TODO.md`](character_pipeline/TODO.md) | Strongest match to your goal: it correctly calls the output blockout, keeps prompt interpretation constrained, and separates mesh review from later stages. | Promote target definition, CPU benchmark, immutable output, and silhouette iteration. Keep expensive mesh QA and downstream stage contracts incremental. Use an approved/manual exemplar to define fidelity, not to replace generator work. |
| [`server/TODO.md`](server/TODO.md) | Confirmed correctness issues and relevant gameplay safeguards. | Forged internal action context and replay rebuild are the only immediate confirmed P1 fixes for current behavior. Session-origin protection is appropriate for the local server; creator/reviewer identity and public-network controls are deployment gates, not requirements for the offline mesh pipeline. |
| [`web/TODO.md`](web/TODO.md) | Findings help avoid misleading or broken interfaces. | Fix Recipe Studio integration/output identity if it affects model builds. Remote-traveler rendering, general accessibility, touch controls, and the separate `web/studio.html` client are not prerequisites for first accepted geometry; prioritize according to active gameplay/UI goals. |
| [`project_contracts/TODO.md`](project_contracts/TODO.md) | Vision, licensing, contract, and release suggestions generally support the project documentation. | Correct factual/documentation mismatches when touched. Defer general release operations and full downstream contracts until deployment or those stages are in scope. Do not create policy/schema machinery without a current tool that consumes it. |
| [`README.md`](README.md) | Properly states the audit scope and evidence limitations. | Keep as provenance for the audit; subsystem reports are TODO guidance, not a replacement for the indexed project documents or the existing root character TODO. |

## Tighten these recommendations before implementation

1. **Priorities:** P0/P1 labels identify seriousness, not work order across
   unrelated tracks. The geometry candidate and gameplay integrity fixes can
   proceed independently.
2. **Candidate isolation:** There are two scopes: draft/trial directories and
   the actual Blender candidate/preview output. Preserve already-unique UI
   trials and fix only the shared build/output path.
3. **Rights:** Require evidence and human attestation, not a claim of automated
   legal verification. Scope hard blocks to third-party-source use, dataset
   eligibility, and redistribution.
4. **Mesh QA:** Do not implement every advanced mesh diagnostic before the
   first useful iteration. Measure CPU cost, keep fast gates mandatory, and
   make costly analysis optional until justified.
5. **Hashing/approvals:** Hash exact inputs and outputs at stage boundaries.
   Append-only review history and authenticated reviewer roles matter when
   multiple users or deployment are in scope; a local single-creator prototype
   can keep a simple local review record, clearly labelled as an attestation.
6. **Duplicate roadmaps:** Keep [`../to_do.md`](../to_do.md) as the detailed
   character execution checklist. This audit report should diagnose risks and
   link into it rather than creating a second checkbox list that diverges.

## Goal-specific acceptance gate

The first character milestone is achieved only when:

- A natural-language brief becomes an explicit, inspectable, versioned recipe;
  unsupported text is preserved and does not alter geometry.
- The same recipe, builder version, and inputs produce repeatable CPU output,
  with measured time/memory on the intended machine.
- Each attempt retains its own mesh, preview, recipe, build plan, and hashes;
  rebuilding cannot overwrite a prior candidate.
- The mesh is a complete T-pose form that matches the agreed Stone Troll
  target from front, side, and back; it passes applicable structural checks
  and receives a human geometry decision.
- It remains honestly labelled as geometry-only and not rigged, textured, or
  runtime-approved.
