# Character recipe observations

This folder is reserved for one versioned observation per independent,
rights-reviewed character source. Files must conform to
[`atlas-character-observation-v1.schema.json`](../../../specs/atlas-character-observation-v1.schema.json).
Technical source dossiers use
[`atlas-character-source-inspection-v1.schema.json`](../../../specs/atlas-character-source-inspection-v1.schema.json).
Every new intake also emits a hash-pinned technical screening report using
[`atlas-character-source-screening-v1.schema.json`](../../../specs/atlas-character-source-screening-v1.schema.json).
The initial feature terms are listed in
[`atlas-character-observation-vocabulary-v1.json`](../../../specs/atlas-character-observation-vocabulary-v1.json).

## What belongs here

Each observation records canonical features, optional normalized measurements,
explicit structural relationships, source/license details, derivation lineage,
and human review status. Use stable concept IDs rather than free-form synonyms.
Record `present`, `absent`, `unknown`, and `not_applicable` separately; a
feature omitted from a description is not evidence that it is absent. The
intake tool puts every vocabulary item in `unknown`; it never assigns anatomy
states automatically. A reviewer can move terms to another state after
examining the source from useful views.

## Intake tool

Run Blender 4.x or newer from the Atlas repository root:

```sh
blender --background --python tools/characters/inspect_character_source.py -- \
  --source /path/to/source.glb \
  --archetype-id humanoid \
  --independent-source-id blender-studio:human-base-meshes-v1.4.1 \
  --focus-object Body \
  --source-title 'Human Base Meshes v1.4.1' \
  --source-author 'Blender Studio and community contributors' \
  --source-license 'CC0 1.0' \
  --source-url 'https://www.blender.org/download/demo-files/' \
  --output-dir data/source_intake/human-base/<source-id>
python3 tools/characters/validate_character_observation.py \
  /path/to/intake-draft/observation.draft.json
```

The first-pass vocabulary and normalization support upright humanoid sources
only; quadruped, dragon, and other archetype vocabularies/reference dimensions
must be defined before those assets are extracted as observations. The tool
supports `.blend`, `.glb`, and `.gltf`, hashes the source file, and
creates `source_inspection.json`, `screening_report.json`, and
`observation.draft.json`. The dossier
reports objects, transforms, bounds, mesh counts, connected components,
boundary/non-manifold/wire edges, zero-area polygons, modifier/UV/color/custom
attribute/material summaries, vertex groups, armature bones, actions, and
whole-mesh world-Z cross-sections. Driver curves and their validity are also
recorded; evaluated counts are marked unreliable if a mesh has an invalid
driver or an unresolved driver target. Local `.gltf` buffers and images are
hashed when their referenced files are present. For a scene with multiple
meshes, select a focus object by its exact Blender object name; without one,
the observation contains no focus-mesh measurements.

The measurements are simple geometric summaries, not anatomical labels or a
complete description from which to reproduce a mesh. For upright humanoids,
the shape profile uses a virtual, uniform height-to-1 normalization with the
horizontal bounding-box center at XY origin and the feet/floor at Z=0. The
source mesh, object transforms, and original file are not rescaled or rewritten;
raw bounds and scene unit metadata remain in the dossier. This normalization
assumes the source is upright in world Z. Pose and facing direction still need
human review. The tool always sets rights to `review_required`, and its output
does not approve the source's license, quality, fit, or runtime suitability.
Keep draft outputs
outside the approved observation collection until source identity/lineage,
rights evidence, geometry, labels, and measurements are reviewed. Never change
the observation review status to `reviewed` until a named reviewer, UTC time,
and rationale are recorded. Validate edited observations with the command
above. Do not feed drafts to a miner.

The screening report checks whether a focus mesh is present and measurable, and
flags boundary/non-manifold/wire edges, zero-area faces, multiple connected
components, and unreliable evaluated geometry for contextual review. It uses
no universal polygon-count threshold. `technically_promising` means only that
the measurable technical checks found no blocking concern; visual quality,
pose, feature visibility, archetype fit, lineage, and rights remain human
review gates. The report always leaves learning eligibility `not_approved`.
Its first profile applies only to general humanoid anatomy references; it does
not establish fitness for a humanoid-specific learning question.

Only reviewed observations with `rights_status: cleared_for_analysis` should
contribute to recipe-mining statistics. Do not count multiple poses, renders,
or derivative meshes from the same original as independent examples. Keep
draft extractions traceable so a reviewer can correct or reject them.

## Relationship learning

The future local miner will find co-occurrence and typed graph patterns across
these observations. It must report the number of independent examples and
eligible denominator, uncertainty, context, exclusions, source IDs, and input
hashes. A mined pattern is a candidate, not a character rule. Human-reviewed
findings may later be promoted into the authored grammar, where they can inform
new recipes as optional, explainable suggestions.

No observation dataset is approved yet. Do not add inferred population rules
or claim the system has learned a pattern until the observation data, miner,
and review process exist.

## Observation versus build recipe

An observation is evidence about a source asset. A build recipe is an
instruction record for a specific reproducible candidate. The cross-category
build contract is documented in
[`atlas-model-recipe-v1.schema.json`](../../../specs/atlas-model-recipe-v1.schema.json).
It can capture dimensions and frames, parameter values and influence weights,
geometry/topology settings, materials and texture hashes, component transforms
and links, UV policy and material assignments, rig, animation and skin-weight
references, variants, collision, LOD/performance limits, validation evidence,
and output checksums. It does not contain the
actual mesh or per-vertex skin arrays; those remain binary asset data or
referenced sidecars. The schema is not wired into a builder yet.
