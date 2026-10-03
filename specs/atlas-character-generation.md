# Atlas character generation workflow

## Pipeline stages

Character creation uses small, reviewable artifacts at each stage:

1. **Brief to design profile.** A user writes a brief in the local Recipe
   Studio or supplies `atlas-character-design-profile/v1` JSON directly. The
   current deterministic text parser recognizes only explicit supported
   measurements and feature toggles; qualitative phrases remain in the source
   prompt and do not become guessed geometry. An optional AI assistant may
   help with ambiguous requests later, but is not required. The profile records the source prompt,
   concise design summary, assumptions, silhouette controls, palette, feature
   modules, and intended actions. The profile is ordinary data; Blender does
   not call an AI model to generate the mesh or animation.
2. **Profile and recipe to base model.** The character profile and compiled
   character recipe can be frozen into an
   `atlas-character-geometry-build-plan/v1`. Blender consumes the plan's
   supported body proportions and canonical T-pose, and checks input and tool
   hashes before building. Choose either the explicit `--allow-blockout`
   procedural path or a separately calibrated and human-approved `.glb` or
   `.blend` geometry seed. The source path records its exact mesh object, file
   hash, license/provenance, calibration record, and design-fit/topology/rights
   review. Blender normalizes the selected source mesh, applies the supported
   body-proportion warp, repositions rigged arms where source bones allow,
   stitches the shoulder/axilla where matching boundary arcs are found, and
   adds requested horns, tusks, or pointed ears. It removes the source rig and
   animations. A front image remains an optional silhouette measurement for
   the procedural path only; it does not create hidden anatomy or surface
   detail. Both paths write review-only `.blend`, static GLB, and provenance
   records under `art/characters/pending_models/`.
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
passed. The former Stone Troll reference calibration was removed during the
rights audit because its source was unavailable. Use only calibrated sources
with documented rights. The profile exposes body
proportions plus muscle definition and jaw, nose, hand, foot, and ear controls. Troll, orc, elf, and goblin
also have modest deterministic silhouette priors; these are starting points,
not species-specific anatomy. Horns, tusks, eyes, brows, and pointed ears are
still simple feature blockouts. The generator does not infer detailed anatomy
from the source prompt or image.
The procedural result is not a finished or universally correct model: the profile
vocabulary and procedural shape library must grow with authored examples and
human review. Source-seeded mode preserves and locally warps the selected source
mesh; it does not retopologize it or guarantee deformation quality. Its
supported proportion controls are a coarse spatial warp, not anatomy-aware
sculpting. Jaw/nose/bust/glute/muscle controls and the base skin palette are not
fully applied to source geometry; horns, tusks, and pointed ears are added as
simple islands when enabled, which may duplicate features already in the source.
Source materials are preserved. Check missing texture paths and inspect the
result before acceptance. A source without usable joint bones must already be
close to the Atlas T-pose; inferred guides are only starting points. Requested actions are recorded for
later rig and animation work; they are not generated at this stage. These
limits are stored with every generated artifact so the preview is not
mistaken for a finished character.

## Generate a base

### Use a reviewed source mesh as the starting point

The source-seeded route is optional and requires a `.glb` or `.blend` source
that has been calibrated and reviewed for rights, design fit, and topology.
Calibration records measurements and source identity; it does not by itself
approve geometry use. For a Blender file, name the exact mesh object and supply
its source title, creator, license, and original URL:

```sh
blender --background --python tools/characters/calibrate_character_reference.py -- \
  --source /path/to/cleared-source.blend \
  --object-name BodyMesh \
  --source-title 'Source title' --source-author 'Creator' \
  --source-license 'CC0' --source-url 'https://example.org/source' \
  --output art/characters/references/calibrations/source.json
```

For `.glb`, the script reads embedded provenance where available; explicit
`--source-title`, `--source-author`, `--source-license`, and `--source-url`
options can supply or correct metadata. Multi-mesh GLBs also require
`--object-name`. Review the resulting measurements and source in Blender. Only
after a human has checked rights, suitability for the intended design, and
topology should the profile declare `reference_calibration.use` as
`geometry_seed` and include `geometry_seed_review` with reviewer, UTC date-time,
three completed review flags, and rationale. Keep `review_only` for sources
used only to measure or inspect.

The profile must point to that exact source file and calibration JSON, include
the source SHA-256 and matching license, and identify the selected mesh object
in the calibration record. Compile the recipe and geometry plan, then build
from the frozen plan:

```sh
python3 tools/characters/compile_character_geometry_plan.py \
  --profile art/characters/profiles/your-profile.json \
  --output art/characters/recipes/your-build-plan.json
blender --background --python tools/characters/generate_character_base.py -- \
  --profile art/characters/profiles/your-profile.json \
  --build-plan art/characters/recipes/your-build-plan.json
```

The builder rechecks source and calibration hashes against the plan. It
normalizes the selected mesh, applies the supported coarse proportion warp,
may reposition arms when usable source bones exist, and adds enabled feature
blockouts. It preserves source materials, removes source rig/animation, and
records provenance and review details. It does not retopologize, guarantee
deformation quality, or make the output runtime-ready. A source with no usable
joint bones must already be near the Atlas T-pose. Generated geometry still
needs human review in Blender. Recipe Studio currently launches only the
procedural blockout path; this source-seeded workflow is driven through the
profile, plan, and Blender command line.

### Run the local Recipe Studio

From the repository root, run:

```sh
python3 tools/characters/recipe_studio_server.py
```

Open <http://127.0.0.1:8766>. The service binds only to loopback and uses no
remote AI or web service. Its chat-style composer currently starts from the
Stone Troll design profile. Use explicit forms such as `height 220 cm`,
`shoulders 125%`, `hands 110%`, `with horns`, or `without horns`. The UI shows
the exact fields changed and requires acknowledgment that unparsed wording is
stored in the brief but does not affect geometry. It compiles a recipe and
hash-bound geometry build plan, then can launch Blender to create a
`blockout_only` candidate. Blender and the local `three` package installed by
`npm ci` are needed for generation and the interactive GLB preview.

The Generated Model Review gallery lists prior successful Recipe Studio builds
from `art/characters/pending_models/recipe_studio/`. Select a candidate to load
its GLB preview and inspect build metadata. **Keep for reference** writes a
review status to that build; it does not certify geometry, rights, learning
eligibility, rigging readiness, or runtime approval. **Delete generated
build** requires browser confirmation and removes only the selected Recipe
Studio build directory. The server validates its draft/build IDs, expected
candidate record, and directory containment before removal. Source assets,
other pending-model folders, and runtime assets are outside this UI's scope.

This is a Stone Troll workbench, not a general natural-language character
understander. If a description says “massive arms,” it will not choose a
percentage for the user. Enter an explicit percentage or keep the phrase only
as source text. The initial build contains no armature, skin weights, or
animation.

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

For recipe-driven generation, compile the profile and grammar into the
traceable character recipe, then compile the recipe and profile into a frozen
geometry build plan:

```sh
python3 tools/characters/compile_character_recipe.py \
  art/characters/profiles/stone_troll.json \
  --output /tmp/stone_troll_character_recipe.json \
  --allow-draft

python3 tools/characters/compile_character_geometry_plan.py \
  art/characters/profiles/stone_troll.json \
  /tmp/stone_troll_character_recipe.json \
  --output /tmp/stone_troll_geometry_build_plan.json

blender --background --python tools/characters/generate_character_base.py -- \
  --build-plan /tmp/stone_troll_geometry_build_plan.json \
  --allow-blockout
```

The geometry plan verifies the recipe schema, recipe-to-profile hash and
character identity, supported parameter ranges, canonical pose, and exact
builder/compiler/schema hashes. Blender rejects a stale plan or changed input.
The generated pending-model directory retains the source profile, character
recipe, build plan, mesh, preview, body-region data, and checksums together.
The builder consumes the recipe's body proportions; anatomy relationship prose
and material tags remain evidence/guidance and are not geometry instructions.
This connects a small, explicit subset of the character recipe to the existing
procedural builder or the reviewed-source warp. It does not execute
`atlas-model-recipe-v1`, produce a high-detail sculpt, or guarantee a
design-perfect mesh. The output is unrigged and unskinned; no Atlas armature,
skin weights, or animation are generated at this stage.

```sh
python3 tools/characters/validate_character_design_profile.py \
  art/characters/profiles/stone_troll.json

blender --background --python tools/characters/generate_character_base.py -- \
  --profile art/characters/profiles/stone_troll.json \
  --allow-blockout
```

`--allow-blockout` is an explicit request for a concept preview. The default
command refuses because this repository does not contain a high-detail mesh
that matches the Stone Troll brief. A licensed source can seed a candidate only
after its design fit, topology, materials, provenance, and license are reviewed
and recorded. Source-seeded outputs remain review candidates, not accepted or
production-ready geometry.

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

### Source observation intake

Source inspection is a separate evidence-gathering step from character
generation. It can create a technical dossier and an observation draft for
`.blend`, `.glb`, or `.gltf` files; it does not generate a recipe, alter source
geometry, infer anatomy, or approve a source. Its current semantic vocabulary
and height-based normalization are restricted to upright humanoids. Other
archetypes need their own versioned feature vocabularies and a meaningful
reference dimension (for example, shoulder height or body length) before
creating observations. Run it from the repository root:

```sh
blender --background --python tools/characters/inspect_character_source.py -- \
  --source /path/to/model.glb \
  --archetype-id humanoid \
  --independent-source-id creator:original-model-id \
  --source-title 'Source title' --source-author 'Creator' \
  --source-license 'License label' --source-url 'https://example.org/model' \
  --output-dir /path/to/draft-folder
python3 tools/characters/validate_character_observation.py \
  /path/to/draft-folder/observation.draft.json
```

For multi-mesh files, pass `--focus-object` with the exact Blender object name
when you want the draft to include basic bounding-box ratios and a whole-mesh
cross-section profile. With no unambiguous focus mesh, it emits no such
measurements. Measurement extraction virtually centers the focus mesh in XY,
places its lowest world-Z point at zero, and scales its world-Z height to one
unit. It does not change the source file, source mesh, or scene transform; the
original bounds and unit metadata are retained. The dossier captures source
hash, object inventory and transforms,
mesh counts, component/topology counts, degenerate faces, modifiers, groups,
attributes, materials, armatures, actions, and those optional geometric
summaries. It records driver curves and marks evaluated geometry unreliable
when a driver is invalid or its target is unresolved. It hashes local glTF
dependencies when available. Height normalization assumes the source is upright
in world Z; it does not pose a rigged source into the canonical T-pose.

Every feature starts `unknown`. A person must inspect useful views and decide
which visible concepts are `present`, `absent`, or `not_applicable`; unshown or
uncertain concepts stay `unknown`. Confirm measurements, source lineage,
provenance, and license evidence separately. Intake always marks rights
`review_required`. Only after human review and validation may an observation
be marked reviewed and considered for a future analysis set; the miner does
not exist yet. Keep intake output in a draft location and never treat a dossier
as a geometry-seed calibration or asset approval.

The current authoring references are listed in
[`../art/characters/sources/README.md`](../art/characters/sources/README.md).
The CC-BY Troll Mauler and CC0 human-base bundle may be inspected locally as
licensed references, but neither has a calibration record or is approved Atlas
geometry. Create a new calibration only from a source with recorded rights,
and retain its source hash and license alongside the measurements. Do not use
Mixamo animation content for recipe learning or AI/ML training.

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
