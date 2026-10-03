# Atlas character generation workflow

## Pipeline stages

Character creation uses small, reviewable artifacts at each stage:

1. **Brief to design profile.** A user or optional AI assistant supplies
   `atlas-character-design-profile/v1` JSON. It records the source prompt,
   concise design summary, assumptions, silhouette controls, palette, feature
   modules, and intended actions. The profile is ordinary data; Blender does
   not call an AI model to generate the mesh or animation.
2. **Profile to base model.** Blender currently creates a low-detail procedural
   blockout only. Generation requires the explicit `--allow-blockout` flag so a
   preview cannot be mistaken for a high-detail production model. An optional
   front image adjusts the blockout's silhouette; it does not create new anatomy. It places
   named landmark guides and writes a review-only `.blend` plus static GLB
   preview under `art/characters/pending_models/`.
3. **Human base review.** Inspect the silhouette and feature placement. Record
   accept or reject with a named reviewer and rationale. Geometry approval
   means only that the base may advance; it does not approve texture, rig, or
   runtime use.
4. **Texture and material review.** After geometry approval, author UVs,
   materials, textures, eyes, hair, and other appearance details. Review this
   output separately; appearance edits must not silently change the approved
   geometry.
5. **Rig marker placement.** Once appearance is approved, move the named empty
   guides in Blender to the character's joints and facial landmarks, then
   export their positions as `atlas-rig-landmarks/v1`. Marker data is a
   separate input artifact linked to the exact reviewed mesh hash. Current
   tooling allows manual placement; AI marker proposals are future work.
6. **Skeleton, weights, and deformation review.** Use the accepted base and
   reviewed landmarks to build or fit the Atlas-compatible skeleton, generate
   skin weights, and inspect representative poses. This remains a distinct
   gate; marker export does not approve a rig.
7. **Animation and runtime export.** With an approved rig, author or retarget
   animation and review required actions. Package only after reviewing
   provenance, rig compatibility, animation behavior, and runtime constraints.
   Registration is a separate release gate.

The existing `atlas-character-profile/v1` is the in-game appearance/save
contract. The design profile defined here is a creator input and does not change
runtime appearance storage.

The body remains one Blender mesh object. This means it is editable and
exportable as one object; it does not promise that every vertex belongs to one
connected, watertight surface. `body_regions.json` assigns semantic face
regions such as head, neck, torso, arms, hands, legs, and feet; `atlas_body_region`
and matching vertex groups carry those labels in Blender. Point landmarks such
as eyes, brows, nose, shoulders, and collarbones are stored as named coordinates
and surface landmarks are projected onto the generated mesh. These labels let
later tools find a region or anchor without guessing from a broad bounding box;
they do not split the body into separate head or torso meshes.

Before writing any review artifact or exporting a preview, generation runs a
structural shoulder gate. It locates the central chest and left/right upper-arm
regions in the normalized mesh, then requires all three to belong to the same
edge-connected component. This catches detached arm sockets while allowing
intentional islands such as eyes, teeth, horns, and source-model details. The
record also reports whole-mesh component sizes, boundary edges, and
non-manifold edges for diagnosis; those global counts are not used as a blanket
failure because reference meshes may contain intentional open or separate
surfaces. A failed shoulder gate stops generation before the output directory
is created. Automated topology checks do not establish good shoulder shape,
deformation, or visual quality; those remain review gates, and rig deformation
checks can only run after a rig exists.

Every generated base uses the canonical `t_pose_fingers_spread` neutral pose:
arms extended horizontally at shoulder height, fingers extended with visible
gaps, and thumbs angled away from the palms. This makes joint placement and
weight review more consistent. The generator's procedural body is only a
blockout. Inspect shoulders, wrists, fingers, and the silhouette in Blender;
the automated shoulder connectivity check cannot judge their shape or fit.
A later pose option may use an A-pose when a specific rig benefits from it,
but T-pose remains the default.

## v1 limits

Procedural mode creates a new blockout mesh from parametric body forms; it is
not a high-detail sculpt or a substitute for authored anatomy and materials.
The generator refuses to create this blockout unless `--allow-blockout` is
passed. Profiles marked `use: review_only` use measurements only. The current
Stone Troll calibration is measurement-only because its source model does not
match the requested design and has unsuitable surface topology. The profile exposes body
proportions plus muscle definition and jaw, nose, hand, foot, and ear controls. Troll, orc, elf, and goblin
also have modest deterministic silhouette priors; these are starting points,
not species-specific anatomy. Horns, tusks, eyes, brows, and pointed ears are
still simple feature blockouts. The generator does not infer detailed anatomy
from the source prompt or image.
The procedural result is not a finished or universally correct model: the profile
vocabulary and procedural shape library must grow with authored examples and
human review. Requested actions are recorded for
later rig and animation work; they are not generated at this stage. These
limits are stored with every generated artifact so the preview is not
mistaken for a finished character.

## Generate a base

The AI response should be one JSON document conforming to
[`atlas-character-design-profile-v1.schema.json`](atlas-character-design-profile-v1.schema.json).
Keep the original user brief in `concept.source_prompt`; put inferred design
choices in `concept.design_summary` and uncertainties in `concept.assumptions`.
The profile should use the supported template and enumerated action/feature
fields. Choose `realistic` unless the prompt explicitly requests a stylized or
low-poly look. Unsupported anatomy requests should remain visible in
assumptions for the human reviewer.

For each brief, ask the AI to return only the profile JSON, preserve the
requested traits and actions, choose explicit colors and supported proportions
(including muscle definition and jaw, nose, hand, foot, and ear sizes), and list every invented detail
under `concept.assumptions`. This keeps the AI step to a small structured
document instead of generated mesh data or long modeling instructions. The
current repository does not call an AI service itself; the assistant or a
future profile-authoring UI supplies this JSON. Geometry generation is local,
deterministic Blender code and does not consume model-generation tokens.

```sh
python3 tools/characters/validate_character_design_profile.py \
  art/characters/profiles/stone_troll.json

blender --background --python tools/characters/generate_character_base.py -- \
  --profile art/characters/profiles/stone_troll.json \
  --allow-blockout
```

`--allow-blockout` is an explicit request for a concept preview. The default
command refuses because this repository does not contain a high-detail mesh
that matches the Stone Troll brief. A valid production source must be reviewed
for design fit, topology, materials, provenance, and license before a profile
can select it as geometry.

The output contains `character_base.blend`, `character_base_preview.glb`, and
`character.json`. It is never added to `web/assets` or the runtime manifest by
the generator. The generator refuses to write these files when the torso and
either upper-arm region are topologically disconnected; inspect the reported
component IDs and source mesh when that gate fails.

### Fit the model silhouette to an image, without AI

For a locally measured reference image, pass a front-view full-body PNG or JPEG:

```sh
blender --background --python tools/characters/generate_character_base.py -- \
  --profile art/characters/profiles/stone_troll.json \
  --reference-image /path/to/stone_troll_front.png \
  --allow-blockout
```

Use a transparent PNG or a plain, contrasting background, with the character
upright, centered, front-facing, and arms in a T-pose. A near-orthographic view
is preferred. Blender decodes the image; ordinary pixel thresholding extracts
its silhouette and measures width at 128 heights. The generator fits those
widths onto the procedural blockout. The image cannot provide hidden depth or
detailed surface geometry.
The fit report and source-image checksum are saved as `image_measurements.json`
beside the pending model. This is local code and does not call an AI model, send
the image to a service, or use text tokens.

A single front image cannot reveal true side or back anatomy. Image fitting
does not synthesize hidden geometry or create a finished sculpt or texture.
Review the result in Blender before acceptance. Input images with busy
backgrounds should first be cut out or made transparent so foreground
thresholding can isolate the character reliably.

## Experimental grammar recipe

The versioned grammar in `art/characters/grammars/` captures shared anatomy
relationships, approved defaults, and archetype rules with evidence and review
status. Compile a design profile into a hashed recipe with:

```sh
python3 tools/characters/compile_character_recipe.py \
  art/characters/profiles/stone_troll.json \
  --output /tmp/stone_troll_recipe.json \
  --allow-draft
```

Draft archetype rules are rejected unless `--allow-draft` is supplied, and a
recipe using them remains review-only. The recipe contract is
[`atlas-character-recipe-v1.schema.json`](atlas-character-recipe-v1.schema.json);
the grammar contract is
[`atlas-character-grammar-v1.schema.json`](atlas-character-grammar-v1.schema.json).
This compiler currently produces a traceable authoring artifact; Blender base
generation still consumes the design profile directly, so the recipe does not
claim to control the generated mesh yet.

The project also defines a broader cross-category build-record schema in
[`atlas-model-recipe-v1.schema.json`](atlas-model-recipe-v1.schema.json). It
holds detailed build controls, measurements, frames, components, materials,
UV policy and material assignments, rig/weight and motion references, variants,
collision, LOD/performance limits, provenance, and QA/output hashes. This is
contract groundwork only: the character recipe
compiler and Blender generator do not yet consume it. The schema keeps
`influence_weight` for recipe composition separate from per-vertex bone weights,
which belong in the exported mesh or a referenced sidecar.

## Review and marker handoff

Open the `.blend`, inspect the preview, and shape the procedural blockout as
needed. Save edits, then refresh the static GLB so review always refers to the
saved Blender file:

```sh
blender --background --python tools/characters/refresh_character_base_preview.py -- \
  --blend art/characters/pending_models/stone_troll/character_base.blend \
  --character-record art/characters/pending_models/stone_troll/character.json
```

After reviewing the refreshed preview, record the explicit gate:

```sh
python3 tools/characters/review_character_base.py \
  --character-dir art/characters/pending_models/stone_troll \
  --reviewer "Reviewer name" --decision accept \
  --rationale "Base silhouette and proportions accepted for rig authoring." \
  --reviewed-sculpt --reviewed-t-pose
```

The review tool rejects generated blockouts by default. After sculpting the
geometry-only base, refresh the preview and inspect it against the reference.
Pass `--reviewed-sculpt --reviewed-t-pose` only after confirming the mesh is
complete, matches the design, has connected hands/wrists/arms, and holds the
required T-pose. These flags record human attestations; they do not automate
visual-quality judgment. Acceptance unlocks rig-authoring work only. It does
not approve textures, runtime use, or release.

The geometry-only mesh is the first quality milestone. Final materials,
textures, skin/hair detail, and other surface work are later stages and are not
required to approve this stage. Free geometry references and their licenses are
listed in [`../art/characters/sources/README.md`](../art/characters/sources/README.md);
neither listed source is an approved Stone Troll result.

## Licensed reference calibration

Use licensed exemplars to measure proportions and compare recipe outputs. Keep
the source file outside runtime assets; the calibration record stores its hash,
embedded source/license attribution, normalized cross-sections, and rest-pose
rig landmarks. It does not copy source geometry, materials, skinning, or motion.

```sh
blender --background --python tools/characters/calibrate_character_reference.py -- \
  --source /path/to/reference.glb \
  --output art/characters/reference_calibrations/reference_name.json

blender --background --python tools/characters/calibrate_character_reference.py -- \
  --source art/characters/pending_models/stone_troll/character_base_preview.glb \
  --output /tmp/stone_troll_generated_calibration.json

python3 tools/characters/compare_character_calibrations.py \
  --reference art/characters/reference_calibrations/troll_sketchfab.json \
  --generated-calibration /tmp/stone_troll_generated_calibration.json \
  --character-record art/characters/pending_models/stone_troll/character.json \
  --output art/characters/reference_calibrations/stone_troll_atlas_comparison.json
```

Licensed references currently support measurements only. A future seed-mesh
path requires explicit asset review; do not promote a measurement reference to
geometry merely because a license permits reuse. Whole-mesh sections can be
skewed by pose, and source bone positions are not Atlas rig targets.

Install `tools/characters/atlas_marker_placement_addon.py` through Blender's
Preferences > Add-ons > Install from Disk, enable **Atlas Landmark Placement**,
and reopen the accepted `.blend`. In the 3D View sidebar under **Atlas
Markers**, choose an eye, brow, nose, elbow, knee, or other named landmark and
move it with the gizmo or `G` then `X`, `Y`, or `Z`. Marker guides stay locked
until the base-review record says accepted. Save the `.blend`, then export:

```sh
blender --background --python tools/characters/export_character_markers.py -- \
  --blend art/characters/pending_models/stone_troll/character_base.blend \
  --character-record art/characters/pending_models/stone_troll/character.json \
  --output art/characters/pending_models/stone_troll/rig_landmarks.json
```

The exporter refuses to run before base acceptance and writes marker coordinates
in root-local meters, applying the generated root scale. Rig generation and weighting consume
this sidecar in a later stage. Marker exports and generated bases remain
authoring artifacts; they do not modify the runtime manifest.
