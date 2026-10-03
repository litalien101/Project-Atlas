# Atlas Reach Visual Direction

## Art direction

**First light in a deep green valley.** The Reach should feel quiet, ancient, and welcoming, with the Listening Beacon as the warm focal point. Use stylized natural forms and broad readable silhouettes. Favor handcrafted color and shape over photorealism or dense surface noise.

## Palette and lighting

- Cool blue-green canopy and distant sky frame a warm sandstone horizon.
- Forest greens stay varied but restrained; the traveler and interactable objects need clear contrast against them.
- Warm directional light comes from a low angle. Cool sky fill keeps shadowed surfaces legible.
- Fog starts beyond the local play space and blends into the horizon palette. It should establish distance without hiding navigation or landmarks.
- The Beacon and Lumen reeds use localized light sparingly to guide attention.

## World composition

- Keep the path readable from the starting area and use it to lead the eye toward the Beacon.
- Trees, grass, flowers, and reeds use deterministic procedural placement so the world remains stable between visits.
- Foliage motion is subtle and slow. Landmark silhouettes remain still and visually distinct.
- Ground color and roughness vary by terrain region; avoid a checkerboard of equally strong tile colors.
- Movement blockers come from the authoritative world description. Decorative details must not silently become client-only collision.

## Camera, movement, and sound

- Use a close third-person follow camera with smooth orbit and zoom. Keep the horizon and nearby landmarks visible while moving.
- Blend character motion from simulated velocity. Keep head bob and procedural limb movement restrained so the camera remains comfortable.
- Build ambience from original or properly cleared sounds. Wind stays low in the mix; occasional wildlife calls should not compete with interaction cues.
- Important interaction sounds and effects should be short and spatially clear.

## Implementation guidance

- Preserve the world-first HUD and keep panels closed until needed.
- Reuse terrain geometry and materials; add detail with a few purposeful silhouettes rather than dense particle effects.
- Maintain readable contrast across bright and dim displays. Do not rely on color alone to communicate interaction state.
- Test on integrated graphics and narrow/mobile viewports before increasing shadow-map, geometry, or post-processing costs.
- Use original procedural art or assets with documented provenance. Do not copy RuneScape or World of Warcraft game assets.
