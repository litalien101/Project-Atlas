# Project Atlas Decision Log

## Decision log

- The unavailable Sketchfab Troll calibration and Bing-generated reference
  images are no longer retained. The pinned CC-BY Troll Mauler and CC0 Blender
  human-base bundle are authoring references only, not the target mesh.
- The base-mesh milestone is geometry-first: a reviewed, design-matched T-pose
  sculpt, deliberately unrigged and unskinned. It is not a textured or
  runtime-ready character; surface detail and later marker-driven rigging
  follow geometry acceptance.
- The intended creator pipeline is request -> structured recipe proposal ->
  deterministic recipe validation/build plan -> Blender mesh -> creator geometry
  approval -> texture/material build and approval -> Mixamo-style visual marker
  placement and approval -> deterministic marker-driven skeleton generation ->
  skinning/deformation review -> animation -> runtime packaging. AI can propose
  recipes and landmarks but cannot approve assets or bypass deterministic checks.
- Prefer deterministic text parsing and recipe compilation for supported
  vocabulary, units, and controls. Prompt the creator to resolve missing or
  conflicting requirements; reserve optional AI assistance for ambiguous or
  unsupported descriptions rather than routine geometry execution.
- The first executable geometry slice is limited to a validated
  `atlas-character-recipe/v1` and source profile compiled into a hash-bound
  `atlas-character-geometry-build-plan/v1`. Blender consumes supported body
  proportions and the canonical T-pose and emits a blockout-only, unrigged
  candidate. The cross-category model recipe and general text parser are not
  implemented; Recipe Studio currently recognizes a small fixed vocabulary.
- A free model's license does not make it design-compatible or Atlas-rig
  compatible; downloaded models remain references until independently reviewed.
- A front image is a measurement guide, not a complete 3D asset. Width fitting
  alone cannot solve the model-quality problem.
- Curate target recipes and rights-cleared independent observations in parallel
  with geometry work. The authored Stone Troll recipe is not statistical
  evidence; do not claim mined findings until reviewed independent examples
  exist.
- Implement recipe learning first as an offline Python library/CLI in the
  repository. A separate network service is unnecessary until scale,
  collaboration, or deployment needs justify one.
- Personality and emotion are persistent simulation state with event-based
  causes, not claims that an NPC is conscious.
- The economy is intended to connect household, town, and city systems through
  goods, currency, and constrained trade routes; begin with a small explainable
  simulation rather than a world-wide opaque optimizer.
- The asset pipeline is ultimately shared by every model category and should
  improve through traceable trial results and reviewed recipe revisions.
- Runtime appearance can respond to long-term simulation state, such as gradual
  species-appropriate hair graying from age or prolonged stress; this is not a
  one-event effect or an implemented feature today.
