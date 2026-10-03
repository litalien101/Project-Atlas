# Atlas Character Technical Specification v1

## Goal

Add visual character customization while preserving the current Mixamo-based
character rigs and the locomotion that already works in The Reach. Customization
must not require Unreal Engine or a change to movement simulation, animation
timing, camera behavior, or network state.

The first runtime slice is cosmetic: it can change a character's appearance and
equipped visuals, but it does not grant inventory items or alter gameplay stats.

## Runtime and master rig

- The target runtime is the existing Three.js browser client.
- `ATLAS_HUMANOID_V1` uses the 67-bone Mixamo-compatible rig carried by the
  current female base and the six bundled locomotion clips.
- The Blender reference is
  [`atlas_humanoid_v1.blend`](../art/characters/atlas_humanoid_v1/atlas_humanoid_v1.blend);
  [`atlas_humanoid_v1.json`](../art/characters/atlas_humanoid_v1/atlas_humanoid_v1.json)
  records its bone hierarchy, rest pose, and equipment sockets.
- The existing animation clips, retargeter, animation controller, and movement
  timing are the reference behavior. Equipment work must not change them.
- Character and equipment files use glTF/GLB, the format already loaded by the
  browser client.
- The skeleton name, parent hierarchy, bind pose, units, forward axis, and root
  convention are part of the versioned contract. A future rig change requires a
  new contract version and an explicit migration/retarget step.
- The v1 reference bind pose and source scale are from the current female base.
  Fit new body and equipment assets to this reference.
- The web client normalizes the female model to 1.68 m at runtime. Keep equipment
  in the reference model's source scale and inherit the same runtime scale.
- All traveler instances use the source in
  [`female_base.blend`](../art/characters/atlas_female_base_v1/female_base_source.blend),
  prepared as a bare skin base on the same Mixamo bone hierarchy. Bra and briefs
  are separate optional equipment meshes in its Atlas export:
  [`female_base_atlas_v1.glb`](../web/assets/characters/female_base_atlas_v1.glb).

## Equipment compatibility

Every skinned equipment asset must:

- use the `ATLAS_HUMANOID_V1` bone names, hierarchy, and bind pose;
- be weighted to that rig and exported in the same coordinate and unit
  convention as the character;
- contain no locomotion animation or root-motion behavior;
- identify its equipment slot and stable asset ID in registry metadata;
- pass the character movement preview with idle, walk, run, jump, fall, and land
  clips before it is admitted to the runtime registry.

Rigid accessories such as weapons may attach to a named bone socket with a
versioned local offset. They do not need a full skin, but they must use the
character's coordinate convention and pass the same animation preview.

Appearance is split into independent choices: skin tone, height, weight/body
build, face, hair style/color, and optional equipment. Equipment slots include
`underwear_top`, `underwear_bottom`, `head`, `hair`, `face`, `neck`, `shoulders`,
`cape`, `chest`, `gloves`, `belt`, `legs`, `socks`, `boots`, `main_hand`, and
`off_hand`. An empty slot is allowed; underwear is never baked into the base-body
mesh. `back`, `pet`, and `mount` are reserved for later work because they have
different attachment and animation needs.

## Character definition and asset registry

Character choices are data, never instructions for directly editing meshes.
Definitions refer only to registered IDs:

```yaml
schema: atlas-character/v1
id: traveler_wayfarer
skeleton: ATLAS_HUMANOID_V1
base_model: atlas.female_base_v1
appearance:
  hair_style: atlas.hair.short_01
  hair_color: chestnut
  skin_tone: warm_03
  height_cm: 168
  weight_kg: 70
  body_build: average
equipment:
  underwear_top: null
  underwear_bottom: null
  head: null
  shoulders: atlas.shoulders.ranger_leather
  chest: atlas.chest.ranger_leather
  legs: atlas.legs.ranger_leather
  boots: atlas.boots.ranger_leather
```

The schema validator checks required fields, allowed ranges, unique IDs,
registered asset references, slot compatibility, skeleton version, and file
checksums. Asset metadata records source, creator, license, modifications,
dimensions, materials, LODs, and compatible slots. Player choices and NPC
appearance state use the same profile format. NPC behavior may request a hair,
clothing, or underwear change by selecting registered asset IDs; it cannot edit
mesh data directly. The world stores the resulting profile with the NPC so its
appearance remains consistent after the character leaves and returns.

## Base-body and clipping policy

The base body is bare, has no baked clothing, and remains the animated body when
the outfit changes. Underwear, socks, shoes, and other clothing are optional
registered meshes, each independently removable or replaceable. Compatible body
coverage regions may be hidden when a garment is equipped to prevent clipping.
Changing appearance never replaces the animated skeleton or animator. The current
preview exposes skin tone, height, weight, bust, stomach, hips, glutes, thighs,
the supplied underwear meshes, and shoulder guards. The `atlas-character-profile/v1`
schema is defined in `atlas-character-profile-v1.schema.json`; the local server
validates complete profiles and stores them with each traveler. Proportion
sliders use hand-authored shape targets on the body and matching underwear; they
are an initial customization range, not a scan-based fitting system. Hair, face,
socks, shoes, and additional clothing choices need registered matching assets
before they can be offered in the profile.

## Offline authoring pipeline

1. Author or adapt a source mesh in a DCC tool while preserving the master rig.
2. Export glTF/GLB and a registry manifest using a repeatable script.
3. Run automated checks for the rig, bind pose, skin weights, materials,
   dimensions, slot metadata, and file integrity.
4. Preview the item on the existing character through all six locomotion states.
5. Review clipping and appearance, then register the approved asset.

Blender may be used for scripted offline preparation. The game runtime does not
depend on Blender, Character Creator, or Unreal Engine.

## First proof

1. Capture the current character's six animation states as the baseline.
2. Add one shoulder accessory or outer-layer item authored for the Mixamo rig.
3. Add a small appearance panel that equips and removes that item visually.
4. Verify that the original character mesh, position, gait speed, transitions,
   and jump/landing timing remain unchanged while the item follows the body.
5. Only after this passes, add more slots and convert the existing modular
   outfit pack. Those parts use a different 65-bone skeleton, so they must be
   explicitly re-rigged to `ATLAS_HUMANOID_V1` or rejected; runtime retargeting
   them as full characters is outside this first proof.

## Asset rights gate

Before incorporating a user-provided or third-party modular pack into a
redistributable build, record and verify its source and reuse rights in
`web/assets/manifest.yaml`. Keep unverified source files outside the served
runtime asset directory.
