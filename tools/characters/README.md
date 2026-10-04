# Character Tools

The current authoring path is Recipe Studio → validated profile → compiled
recipe → frozen build plan → Blender blockout → human review. Start the local
workbench with `python3 tools/characters/recipe_studio_server.py`. It binds to
loopback and does not call a remote service.

The committed neutral profile is a technical starting point, not a designed
character. Replace its brief and values with an approved design before using it
as a candidate target. The deterministic parser maps explicit supported
measurements only. Blender emits `blockout_only` geometry; it does not provide
production topology, final materials, rigging, weights, or animation.

For reference intake, `inspect_character_source.py` creates hash-pinned
technical records and an unknown-by-default observation draft from upright
humanoid `.blend`, `.glb`, and `.gltf` sources. Its screening report is
technical triage only. It does not decide rights, visual quality, source
lineage, anatomy labels, learning eligibility, or runtime approval.

See [`../../specs/atlas-character-generation.md`](../../specs/atlas-character-generation.md),
[`../../art/characters/recipe_observations/README.md`](../../art/characters/recipe_observations/README.md),
and [`../../specs/source-model-intake-lifecycle.md`](../../specs/source-model-intake-lifecycle.md).

# Scripted MPFB character prototype

The fastest current route to repeatable rigged humanoids is a recipe-driven
MPFB build. `build_mpfb_character.py` is an isolated proof of concept; it does
not yet replace the general design-profile/blockout pipeline.

Requirements: Blender 4.2 or newer, MPFB enabled in that Blender installation,
and the MakeHuman system asset pack installed. Run from the repository root:

```sh
blender --background --python tools/characters/build_mpfb_character.py -- \
  --recipe art/characters/recipes/mpfb_prototype.json
```

The default build writes directly to the shared project workspace at
`art/characters/exports/<character_id>/`. It includes the skinned `.glb`, an
editable `.blend`, a Blender inspection `.blend` with rig bones hidden by
default in the viewport, and a `build.json` manifest. This export folder is excluded from Git. Use
`--output-dir` to choose another location. Change numeric macro controls and the
skin, hair, shirt, and pants asset names in the recipe to generate variations
without editing the mesh in Blender.

## Review and failure loop

Treat every build as a candidate until its saved Blender inspection file and
GLB have been reviewed. If a candidate fails, record a specific failure code,
what the review showed, and the generator rule that prevents it; then archive
it before rebuilding. For example:

```sh
python tools/characters/archive_failed_candidate.py \
  --candidate-dir art/characters/exports/mpfb_female_prototype \
  --finding 'body_mask_removed_skin_at_opening|Review render showed skin cut away at the collar.|Keep body vertices within 40mm of open garment boundaries.'
```

The archiver verifies the output hashes against `build.json`, preserves that
manifest and the failure evidence under `art/characters/failure_records/`, and
removes the rejected `.blend`, `.glb`, and Blender backup files from both
`exports/` and `pending_models/`. Add the corresponding prevention rule to the
generator before producing the next candidate. Keep only the current review
candidate in `exports/`; do not preserve rejected model binaries there.

This prototype uses MPFB's supported macro controls (gender, age, muscle,
weight, proportions, height, and related controls) plus replaceable system
assets. It intentionally rejects unrecognized fields and free-form anatomy
descriptions. Categorical modules cover hair and independent shirt and pants
slots. The prototype recipe uses garments from MakeHuman Community's CC0
`pants01` and `shirts01` packs; install those packs in MPFB's asset library
before building. Each garment is a separate object, allowing independent
selection and replacement. Check the license on every asset from other packs;
community contributions can have different terms. Armor, ears, eyes, and
attachment compatibility are future work. Generated assets remain pending
until visual, license, animation, clothing-fit, and runtime review is recorded.
The editable `.blend` keeps the source-resolution maps. The exported GLB caps
most textures at 1024 pixels per longest edge and keeps the ponytail's 2048 map
to preserve its hairline. Solid skin and clothing materials export opaque, and
the builder masks base-body vertices under clothing. The known fisherman
sweater/wool-pants pair also overlaps the pants top inside the sweater hem. These
steps address alpha sorting, body poke-through, and the exposed pants waistband
in this prototype. The body mask also keeps a 40 mm clearance from open garment
edges so it does not cut skin at the collar, cuffs, or hem; inspect other
garment combinations individually. The builder records texture dimensions and
an estimated decoded RGBA8 and mip-chain
cost in `build.json`; read the current manifest for the actual regenerated
sample measurement. This estimate is not a final device budget. The GLB
exporter may truncate meshes with more than four joint influences; inspect
deformation before accepting the export. For runtime, measure on target
hardware, use GPU-compressed KTX2 textures where supported, and add distance-
based mesh and texture levels. File compression alone does not guarantee lower
GPU memory.

Eyebrows and eyelashes currently come from low-detail MPFB system assets. The
builder preserves those assets and does not claim they look like groomed 3D
hair; replace them with higher-quality licensed geometry/cards in a separate
asset-quality pass.

GLB does not store Blender's armature viewport "In Front" setting, and Blender
enables it when importing a rigged GLB. The build automatically creates
`*_blender_view.blend` beside the GLB, hides the armature object in its default
viewport without removing the skinned rig, and records the view file hash in
`build.json`. Unhide the armature in Blender when editing the rig. For another
GLB viewer, the exported model and rig are unchanged; this is a Blender
viewport display setting.

The 53-bone rig is simply MPFB's current game-engine preset. No Atlas rig
contract or animation list has been chosen, so do not treat this count as a
final requirement. Choose animation needs first, then verify retargeting,
deformation, and whether facial or twist bones are needed.

See [`specs/atlas-character-generation.md`](../../specs/atlas-character-generation.md)
for the broader pipeline boundary and next steps.

Superseded failed builds are removed after their manifests, failure evidence,
and artifact hashes are recorded in
[`art/characters/failure_records/README.md`](../../art/characters/failure_records/README.md).
