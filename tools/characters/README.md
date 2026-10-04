# Character tool status

Use this page to distinguish current tools from legacy scripts. Detailed
workflows and contracts are linked from [`../../MASTER_FILE.md`](../../MASTER_FILE.md).

## Current intake workflow

Run the local Recipe Studio with the instructions in the
[project README](../../README.md#recipe-studio). The landing page is a compact
3D review workspace for local Troll Sample 1 remesh trials. When a reviewed
candidate is available, select its GLB, pin features or trace separation paths
on the surface, and describe the intended edit. Saved 3D annotations live under
`data/model_reviews/troll_sample_1/`. The model's Blender project is available
from the viewer. Source-derived Troll Sample 1 meshes are not included in the
public repository while their rights and provenance remain uncleared, so the
review list is empty in a fresh checkout until a rights-reviewed candidate is
supplied locally. The recipe builder remains at
`http://127.0.0.1:8766/builder`.

- `inspect_character_source.py` creates a source dossier, technical screening
  report, and unknown-by-default observation draft for humanoid `.blend`,
  `.glb`, and `.gltf` sources.
- `character_source_screening.py` supplies explainable technical triage used by
  the intake command. Its result is not visual-quality, rights, lineage,
  learning, geometry-seed, or runtime approval.
- `validate_character_observation.py` validates the observation data contract
  and the human-review fields. It does not certify the truth of a review.

See [`../../art/characters/recipe_observations/README.md`](../../art/characters/recipe_observations/README.md)
and [`../../specs/source-model-intake-lifecycle.md`](../../specs/source-model-intake-lifecycle.md)
for the acquisition-to-observation handoff.

## Retired clothing and humanoid tools

The old female-base builder, humanoid rig builder, region-map builder, vest
generator, clothing preparation tool, and clothing registration tool were
removed. They depended on a base mesh, rig, or region map that is no longer
retained and cannot be used in the current workflow. Their removal is recorded
in [`../../CHANGELOG.md`](../../CHANGELOG.md); Git history preserves the former
implementation.

There is currently no clothing preparation or registration workflow. Resume
that work only after a licensed replacement base and rig pass review and the
new tools implement the active stage contracts. The current geometry workflow
and source-intake tools above remain available.
