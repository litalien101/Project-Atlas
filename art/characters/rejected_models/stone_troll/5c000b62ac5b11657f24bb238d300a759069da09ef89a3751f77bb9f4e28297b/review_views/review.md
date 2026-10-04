# Stone Troll geometry trial review

**Decision:** Rejected as a geometry candidate; do not advance to texturing,
rigging, animation, or runtime registration.

**Review type:** AI-assisted visual inspection of saved workbench renders. This
is not a human approval and does not change the candidate record into an
accepted state.

- **Reviewed preview:** `character_base_preview.glb`
- **SHA-256:** `5c000b62ac5b11657f24bb238d300a759069da09ef89a3751f77bb9f4e28297b`
- **Source mode:** deterministic procedural parametric blockout
- **Recorded quality tier:** `blockout_only`; `production_ready: false`

## Evidence

Reviewed the saved front, side, back, and three-quarter views rendered from
`character_base.blend`. The views show a complete upright, unrigged T-pose, but
the visible form does not meet the authored brief's grounded, detailed troll
silhouette:

- The hands read as rounded mitten-like masses. Individual fingers and thumbs
  are not clearly separated, so the requested detailed hands and visible
  fingers-spread pose are not demonstrated.
- The side and three-quarter views show large spherical shoulder/upper-arm
  transitions. The arms read as long, straight tubes rather than grounded
  anatomy.
- The front and back views show a sharply pinched waist and a small head over
  a broad, simplified torso. The silhouette is visibly schematic.
- The horns read upright in the front view rather than short and swept back.
  The ears read as very large triangular points. The face and tusks also read
  as simple oversized primitives rather than the requested calm, detailed
  expression.
- The render set has no close views of hands, shoulders, or facial features;
  the existing views are enough to reject this candidate but not to approve a
  revised one.

The character record reports one connected body surface and a passing sampled
shoulder-core connection. Those structural checks do not resolve the visible
shape and design-fit failures. The body is still explicitly a blockout.

No approved, rights-cleared target design sheet or exemplar is available, so
this review makes no claim about exact design fidelity. The rejection is based
on visible mismatches with the authored brief and review criteria, not on an
unverified comparison to external art.

## Disposition and next gate

This trial is preserved here under its preview hash for provenance and future
comparison. Do not reuse it as a seed or treat it as an approved example. Keep
the authored Stone Troll profile separate from this rejected output.

Before generating a replacement, establish an owner-approved visual target
with documented usage rights and choose a modeling approach capable of
matching it. The current retained Troll Mauler and human-base sources are
authoring references, not approved matching geometry seeds. A replacement
must be a new trial with a new output hash and must receive a fresh review.
