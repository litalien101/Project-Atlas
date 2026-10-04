# Character Pipeline Work Queue

## Current baseline

A neutral parametric humanoid profile and local deterministic Recipe Studio
form the current authoring scaffold. No finished character design or accepted
mesh is present. Blender output is a `blockout_only` candidate and must not be
registered as runtime content without review.

## Priority sequence

1. Approve the new character brief, references, silhouette targets, scale, and
   required visible features.
2. Evaluate the locally documented MakeHuman/MPFB and Blender Studio bases;
   choose a rights-reviewed, topology-stable starter and pin its source hash
   and toolchain version.
3. Prototype a small, named parameter catalog mapped deterministically to
   artist-authored shape targets on the unchanged base topology. Define units,
   ranges, defaults, and known compatibility constraints.
4. Validate target combinations and inspect the mesh from multiple views before
   expanding the parameter catalog. Add categorical parts such as eyes, ears,
   hair, and clothing as compatible modular assets, not continuous sliders.
5. Record immutable build inputs, output hashes, visual review views, and
   accept/reject decisions tied to candidate IDs.
6. Retire the current metaball preview when the shape-target prototype meets the
   approved geometry bar. Then implement separate materials, marker placement,
   rig and weight generation, deformation review, and animation stages.
7. Expand source observations only with verified rights, independent lineage,
   explicit measurements, and human-reviewed labels. Keep inferred rules
   evidence-backed and optional.

## Guardrails

- Do not treat a prompt parser as an AI model or infer numeric anatomy from
  adjectives.
- Do not treat generated revisions as independent source observations.
- Do not use reference assets as geometry seeds without explicit provenance,
  license, topology, and design-fit review.
- Keep project-specific character design separate from reusable pipeline
  contracts and templates.
