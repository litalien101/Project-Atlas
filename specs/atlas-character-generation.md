# Character Generation Workflow

## Purpose and boundary

This document describes the currently implemented local character-authoring
slice. It is a deterministic profile-to-blockout pipeline, not a natural-
language 3D model generator. The committed starter profile is neutral technical
scaffolding. Replace its brief with the approved character design before
creating an authored candidate.

The pipeline preserves the original brief and applies only explicit supported
measurements. It does not infer proportions from adjectives, call a remote AI
service, learn geometry from the source-model library, or create production
retopology, final materials, a rig, weights, or animation. The current Blender
builder is a metaball blockout; the parameter-to-shape-key system described
below is the recommended next implementation, not an existing capability.

## Recommended parameter-to-shape-key route

Use one rights-reviewed, topology-stable base mesh. Store continuous controls
as named, bounded values in the profile and map them deterministically to
artist-authored shape targets. Keep the target catalog explicit: parameter ID,
units/range/default, target name, base-mesh and topology version, and known
compatibility constraints. Start with a small set of body proportions and
facial controls, then review combinations before adding more targets.

Treat categorical changes such as eye style, ear form, hair, or clothing as
separate modular assets with compatibility and attachment rules. They are not
continuous shape-key values. Keep target authoring, profile parsing, Blender
application, and visual acceptance as separate stages. Avoid promising
hundreds of controls until target interactions, topology, clothing fit, and rig
behavior are measured.

MakeHuman/MPFB is a practical reference implementation to inspect: its docs
describe targets as vertex offsets and higher-level phenotype controls as
combinations of targets. The locally retained MakeHuman starter scenes may be
evaluated as candidates, but their presence does not approve them as this
pipeline's base. Blender shape keys preserve a fixed vertex layout and can be
exported as glTF morph targets, so the same authored controls can support a
browser runtime after validation. See [MPFB targets and blendshapes](https://static.makehumancommunity.org/mpfb/docs/assets/concept_targets.html),
the [Blender shape keys manual](https://docs.blender.org/manual/en/4.5/animation/shape_keys/introduction.html),
and [Blender's glTF exporter documentation](https://docs.blender.org/manual/en/5.3/addons/scene_gltf2.html).
The locally retained MakeHuman starter scenes may be evaluated as candidates,
but their presence does not approve them as this pipeline's base. See the
workspace [`Reference_Assets` source register](../../Reference_Assets/ASSET_LICENSE_REGISTER.md).

## Contracts and artifacts

- `specs/atlas-character-design-profile-v2.schema.json` validates design intent,
  the supported humanoid template, body measurements, preview colors, and
  requested actions.
- `art/characters/profiles/starter_humanoid.json` is an undesigned neutral
  starting profile. It is not an approved character brief or geometry target.
- `tools/characters/deterministic_recipe_compiler.py` maps a narrow set of
  explicit measurements to profile fields. Unparsed language is retained as
  source text; ambiguous, conflicting, or out-of-range values block planning.
- `tools/characters/compile_character_recipe.py` compiles the profile against
  the versioned grammar and records input hashes.
- `tools/characters/compile_character_geometry_plan.py` freezes the profile,
  recipe, schemas, and generation options into a hash-checked build plan.
- `tools/characters/generate_character_base.py` creates the Blender candidate
  when explicitly invoked with `--allow-blockout`.

Profiles, recipes, build plans, generated candidates, human review records, and
runtime registrations are separate artifacts. A later stage must not overwrite
an earlier candidate.

## Local authoring

Start Recipe Studio at the repository root:

```sh
python3 tools/characters/recipe_studio_server.py
```

Open <http://127.0.0.1:8766>. The supported text format uses explicit values,
for example `height 175 cm`, `shoulders 105%`, or `hands 100%`. The exact
supported controls and ranges are enforced by the profile schema. Qualitative
phrases remain in the brief and do not alter geometry. Resolve parser questions
and review the structured profile before compiling a plan.

Recipe Studio stores drafts under `data/recipe_studio/drafts/` and generated
candidates under
`art/characters/pending_models/recipe_studio/<draft-id>/<build-id>/`. Each build
has a unique identifier. The gallery can preview a build, record a local
keep-for-reference decision, or remove only that generated build. Keeping is
not geometry acceptance, runtime approval, or publication.

## Command-line blockout

Validate the starter profile:

```sh
npm run characters:profile-check -- art/characters/profiles/starter_humanoid.json
```

Generate a candidate in the pending-model area:

```sh
blender --background --python tools/characters/generate_character_base.py -- \
  --profile art/characters/profiles/starter_humanoid.json \
  --allow-blockout
```

The output record identifies the quality tier as `blockout_only`. Inspect the
mesh and saved views before treating it as useful. Structural topology checks
do not establish design fit, visual quality, or deformation suitability.

## Optional calibrated geometry seed

The command-line builder retains an advanced path for a separately calibrated
`.blend` or `.glb` source. It requires a matching source hash, documented
provenance and license, supported calibration measurements, and a human
attestation covering design fit, topology, and rights. It applies only coarse
supported shape changes; it does not retopologize or make the source
production-ready. Recipe Studio does not expose this path. A seed-based draft
still requires the same visual review and release gates as a procedural build.

## Reference intake

`tools/characters/inspect_character_source.py` accepts upright humanoid
`.blend`, `.glb`, and `.gltf` sources and emits hash-pinned technical records
and an unknown-by-default observation draft. Intake is not a source license
check or visual approval. Before using a source, record its provenance, exact
license evidence, permitted uses, and lineage. A person must review source
geometry, measurements, labels, and intended use before an observation can
inform a recipe. The source library is not an implicit training set.

## Acceptance and release

1. Approve the design brief, scale, coordinate frame, neutral pose, and review
   views before judging a candidate.
2. Inspect geometry visually from front, side, back, and three-quarter views;
   review connected regions, boundaries, normals, and the target silhouette.
3. Record acceptance or rejection against the candidate ID and checksum.
4. Keep material, rig, weight, deformation, animation, and runtime release
   decisions in their own stage records.
5. Register a candidate for runtime only after applicable asset, provenance,
   license, and release checks pass.

Passing a technical check or keeping a candidate for reference does not waive
human design review. No generated starter profile or candidate in this reset
is accepted for runtime use.
