# Atlas Character Technical Specification v1

## Status

This document describes a future character-runtime contract. The previous
female-base model, its model-derived humanoid rig, underwear, body-region map,
and derived vest files were removed because their ownership and reuse rights
were not documented. No Atlas character model or rig is currently registered
for runtime use. The 67-bone model-specific bind pose and scale described by
older prototypes are not an active contract.

The browser keeps server-authoritative movement and animation-retargeting code,
but it has no licensed character mesh to load. A replacement must have a
verifiable license or original authorship, a versioned rig/rest-pose contract,
validated skinning, explicit provenance, and a human-reviewed geometry gate
before it is registered.

## Future contract requirements

- Use glTF/GLB for browser character and equipment assets.
- Version the skeleton name, hierarchy, bind pose, units, forward axis, and root
  convention. A rig change requires a new contract and explicit migration or
  retargeting.
- Keep character choices in data that references registered asset IDs; never
  treat a profile as permission to edit a mesh directly.
- Keep clothing, accessories, and appearance variants as separately reviewed
  artifacts with source, creator, license, modifications, dimensions, and
  checksums.
- Validate skin weights, deformation, fit, clipping, and target-runtime loading
  before registering an asset.
- Do not offer raw third-party source packs for download unless their license
  explicitly allows that redistribution.

## Mixamo animation use

The previous Mixamo clips were removed from the repository because raw
standalone redistribution is not part of the permission the project intends to
rely on. If Mixamo clips are later acquired for a character, document their
game-use scope and exclude them from AI/ML training under Adobe's terms.

## Deferred customization

Body shape, skin tone, face, hair, and equipment controls should only be
connected to registered assets that expose those variants. Until a licensed
replacement model passes review, the former female-base controls are not a
working visual customization pipeline.
