# Character Pipeline Review

## Current state

Atlas has a neutral parametric profile, a deterministic compiler for explicit
measurements, a versioned recipe/build-plan flow, and a Blender blockout
builder. Recipe Studio can preview local builds and preserve a keep-for-
reference decision. Source intake creates technical dossiers and unreviewed
observation drafts.

The baseline is not the new character concept. The mesh builder remains a
low-detail metaball blockout and does not deliver production topology, final
materials, a rig, weights, or animation. A topology report cannot substitute
for visual review or design approval. Source intake does not approve rights,
visual quality, lineage, or learning use.

## Recommended sequence

1. Approve a concrete brief and visual references before tuning geometry.
2. Identify dimensions, coordinate frame, neutral pose, visible anatomy, and
   review views as explicit profile/build contracts.
3. Implement predictable shape controls and topology-aware construction; keep
   all unimplemented controls out of the profile schema.
4. Freeze each build's profile, recipe, schema, generator version, output hash,
   and review record.
5. Require visual and structural review for geometry acceptance; use separate
   decisions for materials, rigging, animation, provenance, and runtime release.
6. Review rights and source lineage before using a reference as a seed or
   observation. No model should silently become a training example.

## Acceptance boundary

A generated blockout is only a review candidate. `kept_for_reference` records a
local decision and does not accept, publish, or register a model. Runtime use
requires the independent asset and release process documented in
`specs/asset-provenance.md`.
