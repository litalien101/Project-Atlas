# Character tool status

Use this page to distinguish current tools from legacy scripts. Detailed
workflows and contracts are linked from [`../../MASTER_FILE.md`](../../MASTER_FILE.md).

## Current intake workflow

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

## Legacy scripts retained for reference

The following scripts depend on a female base, rig, or region map that was
removed during the rights audit. They are **retired and unsupported**; do not
run them as part of current character authoring:

- `build_atlas_female_base_v1.py`
- `build_atlas_humanoid_v1.py`
- `build_body_region_schema.py`
- `generate_wayfarer_vest_seed.py`
- `prepare_clothing_asset.py`

They remain in the repository as historical implementation references. Any
replacement must target a newly reviewed, rights-cleared base and rig, with
updated contracts and explicit validation before being called active.

`register_clothing_asset.py` is a separate manifest/release utility, but no
current character mesh is registered for it to admit. It is not part of the
active intake or geometry-review workflow.
