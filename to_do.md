# Character Pipeline Work Queue

## Current baseline

A neutral parametric humanoid profile and local deterministic Recipe Studio
form the current authoring scaffold. No finished character design or accepted
mesh is present. Blender output is a `blockout_only` candidate and must not be
registered as runtime content without review.

## Priority sequence

1. Approve the new character brief, references, silhouette targets, scale, and
   required visible features.
2. Expand the MPFB recipe into a versioned character contract and reliable
   command-line build. Keep parameter names and ranges explicit; add only
   controls supported by the base system and validated output.
3. Choose the minimum target device/browser and expected visible character
   counts. Establish scene and per-character memory/frame budgets from a
   measured prototype, as described in `specs/character-performance-budget.md`.
4. Add GPU-compressed texture output and compatible LODs, then validate image
   quality, memory, frame time, skinning, and morphs in the browser.
5. Choose the required character actions and animation style; define the rig
   contract and bone mappings from those needs, then verify representative
   deformation. Add modular game clothing/armor and compatible head/ear options.
6. Record immutable build inputs, output hashes, visual review views, and
   accept/reject decisions tied to candidate IDs.
7. Retire the current metaball preview when the scripted MPFB build meets the
   approved geometry bar. Keep rig/weight, deformation, and animation stages
   independently reviewable.
8. Expand source observations only with verified rights, independent lineage,
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
