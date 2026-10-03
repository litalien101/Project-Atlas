# Atlas clothing authoring workflow

Atlas uses a versioned body-region map plus Blender authoring and validation.
Artists still define garment shape and details. The preparation script uses
declared anatomical regions to constrain surface correspondence, transfers rig
weights and morph targets, and exports only to a pending-artifact directory.
Runtime registration is a separate review-gated step.

## Make a working file

Open `art/characters/atlas_female_base_v1/atlas_female_base_v1.blend` in Blender
and save a copy under `art/characters/workspaces/`. Keep the Atlas body and
`ATLAS_HUMANOID_V1_RIG` in the file. Hide the existing underwear meshes while
modeling if they get in the way.

For a fitted garment, artists may duplicate body faces as a starting point, but
must shape and finish the garment silhouette deliberately. Add thickness,
sleeves, panels, seams, and other details. Name the final mesh object (for
example, `shirt_basic`) and keep it positioned around the body in its neutral
pose. Face duplication alone is not a garment generator: cut boundaries,
armholes, hems, and disconnected components require authoring and review.

## Body-region contract

The canonical sidecar is
`art/characters/atlas_female_base_v1/atlas_body_regions_v1.json`. Rebuild it
after changing the base model with:

```sh
blender --background --python tools/characters/build_body_region_schema.py
```

Its polygon indices are tied to the base GLB checksum. Regions are assigned
from the rig's dominant skinning influences. A chest asset must declare `torso`;
gloves declare a hand region. The preparation tool does not infer a region from
a guessed bounding box. The head region does not define brow or other facial
landmarks; those precise placement anchors need to be authored separately.

The Wayfarer vest seed uses torso and proximal shoulder faces only. Its upper
edge is limited by the rig's left/right shoulder-bone landmarks at the
collarbone. It deliberately excludes head-region faces: that region includes
the lower face and is not a reliable neck-only mask.

## Prepare and export

From the project root, run Blender with the working copy and garment object:

```sh
blender --background --python tools/characters/prepare_clothing_asset.py -- \
  --blend art/characters/workspaces/shirt_basic.blend \
  --garment shirt_basic \
  --slot chest \
  --region torso \
  --asset-id atlas.clothing.shirt_basic_v1
```

Declare every region the asset covers by repeating `--region`. Slot-region
combinations are checked against the character contract. The script rejects a
stale body-region map, vertices farther than the configured region offset, and
garment vertices that penetrate the declared body surface past tolerance. It
also checks the Atlas rig, caps influences at four, transfers weights and
morphs, and writes a prepared `.blend`, skinned `.glb`, and JSON metadata into
`art/characters/pending_equipment/` by default. The artist's working file is not
overwritten. Pending files are not runtime assets and do not appear in game.

The supplied `../../Reference_Assets/characters/male_warrior.glb` has matching
bone names and hierarchy; pass its imported body and rig names with `--body` and
`--rig`. It has no body shape keys to transfer.

## Review and registration

Open the prepared `.blend`; inspect every body morph at low and high values.
Preview idle, walk, run, jump, fall, and land. Inspect the whole silhouette,
hem, armholes, disconnected pieces, clipping, stretching, flipped surfaces,
and deformation. Automated region and penetration checks cannot certify the
visual garment shape.

After review, record all six locomotion states and the morph/fit results in a
review checklist. `tools/characters/register_clothing_asset.py` requires that
checklist, a named reviewer, and an explicit redistribution-rights confirmation
before copying an asset into `web/assets` and the manifest. The local server
serves clothing only when its manifest entry is approved. The release asset
check also rejects unapproved clothing.
