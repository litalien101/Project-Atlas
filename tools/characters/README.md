# Character tool status

Use this page to distinguish current tools from legacy scripts. Detailed
workflows and contracts are linked from [`../../MASTER_FILE.md`](../../MASTER_FILE.md).

## Current intake workflow

Run the local Recipe Studio and its generated-model review gallery with the
instructions in the [project README](../../README.md#recipe-studio). The gallery
is limited to successful Recipe Studio builds; it does not browse source
downloads or other pending-model collections.

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
