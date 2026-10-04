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

The build writes an editable `.blend`, a skinned `.glb`, and a `build.json`
manifest under the ignored `art/characters/pending_models/mpfb_prototype/`
directory. Supply `--output-dir` to choose another location. Change numeric
macro controls and the skin, hair, shirt, and pants asset names in the recipe to
generate variations without editing the mesh in Blender.

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
textures at 1024 pixels per longest edge and marks meshes double-sided for
viewer compatibility. The regenerated sample is 9 MiB; its eight maps estimate
26 MiB decoded as RGBA8 or 34.7 MiB with a full mip chain. This is still a
prototype measurement, not a final device budget. The GLB exporter also warns
that some meshes have more than four joint influences and truncates to four;
inspect deformation before accepting the export. For runtime, measure on target
hardware, use GPU-compressed KTX2 textures where supported, and add distance-
based mesh and texture levels. File compression alone does not guarantee lower
GPU memory.

GLB does not store Blender's armature viewport "In Front" setting, and Blender
enables it when importing a rigged GLB. To inspect the model in Blender without
rig controls drawing over the face and body, create and open the companion view
file:

```sh
blender --background --python tools/characters/prepare_gltf_blender_view.py -- \
  --input art/characters/pending_models/mpfb_prototype/<build-id>/mpfb_female_prototype.glb
```

The script saves `*_blender_view.blend` beside the GLB, hides the in-front rig
overlay, and records the view file hash in `build.json`. For another GLB viewer,
the model mesh itself is unchanged; this is a Blender viewport display setting.

The 53-bone rig is simply MPFB's current game-engine preset. No Atlas rig
contract or animation list has been chosen, so do not treat this count as a
final requirement. Choose animation needs first, then verify retargeting,
deformation, and whether facial or twist bones are needed.

See [`specs/atlas-character-generation.md`](../../specs/atlas-character-generation.md)
for the broader pipeline boundary and next steps.

Superseded failed builds are removed after their manifests, failure evidence,
and artifact hashes are recorded in
[`art/characters/failure_records/README.md`](../../art/characters/failure_records/README.md).
