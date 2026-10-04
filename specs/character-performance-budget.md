# Character quality and performance plan

## Goal

Keep close characters visually rich while the average machine loads only the
geometry, textures, and animation work needed at its current camera distance.
Measure browser download size, decoded CPU image memory, GPU texture memory,
geometry buffers, and per-frame CPU/GPU cost separately; one number cannot stand
in for the others.

## Measured MPFB prototype baseline

The local recipe proof exports a 21.9 MiB GLB with eight PNG images. Their
dimensions imply about 134 MiB of RGBA8 texture storage before mipmaps, or about
179 MiB with a full mip chain. One clothing normal map is 4096×4096. This is
too expensive to use as-is for a typical game character, even though the file
download is only about 22 MiB. The exact estimates are recorded in each
generated `build.json`; actual GPU usage depends on image formats and hardware.

The exporter also reports some vertex sets have more than four joint
influences and drops extras. Treat the rig, weights, outfit fit, morph data,
visual style, and performance as unapproved until reviewed in Atlas.

## Recommended production path

1. **Author detail once, ship the efficient version.** Keep a high-detail sculpt
   as an authoring source and bake its surface detail into tangent-space normal
   maps on a clean game mesh. Spend polygon budget on silhouette and joints that
   deform; avoid shipping subdivision-level sculpt geometry by default.
2. **Use GPU-compressed textures.** Convert suitable color, normal, and packed
   material maps to KTX2/Basis and load them through Three.js `KTX2Loader`.
   This can reduce both transfer and GPU texture storage; JPEG/WebP only reduce
   file size while the browser still expands images to GPU textures. Preserve
   uncompressed authoring sources. Keep 4K maps for a measured close-up need;
   start with 2K for the hero and 1K for less visible/shared modules, then
   profile on target devices.
3. **Build mesh LODs offline.** Keep authored modules separate, then generate
   compatible LOD0/LOD1/LOD2 exports with silhouette-aware decimation and
   rechecked skin weights. Choose levels by projected screen size and measured
   frame time, not universal distance or polygon-count recipes. Consider an
   impostor only for crowds at distances where it still looks acceptable.
4. **Share resources.** Reuse the same rig definition, geometry, materials,
   texture atlases, and module assets across characters where their appearance
   permits it. Use atlases and fewer material slots to reduce state changes;
   modularity does not require every part to have a unique texture.
5. **Keep customization bounded.** Apply body recipes offline when making a
   fixed NPC variant. At runtime, retain only morph targets needed for player
   customization; each morph can add vertex-buffer and skinning work. Reuse one
   compatible skeleton, but set its final bones only after the required
   character actions and animation style are chosen.
6. **Load only the active area.** Add distance/visibility-based model and
   texture loading when the world and character counts need it. Virtual texturing
   and large-scale crowd instancing are later options, not prerequisites for a
   good first character pipeline.

## Performance acceptance

Before selecting numeric budgets, choose the minimum target device/browser and
the expected simultaneous close, medium, and distant character counts. Then
measure a representative scene on that device with the browser profiler:

- transferred bytes per character and per outfit/module set;
- decoded image bytes and estimated/observed GPU texture allocation;
- geometry, morph-target, and skeleton buffer bytes;
- draw calls, visible triangles, frame time, load time, and peak memory;
- visual quality in motion at each LOD and texture level.

Set an explicit total scene budget from those measurements, reserve memory for
the world/UI and browser, and divide the remainder among visible characters.
Do not approve the current 22 MiB/179 MiB prototype as a shipped character
budget. Three.js supports KTX2/Basis through `KTX2Loader`, which must be
configured on `GLTFLoader` before assets using `KHR_texture_basisu` are loaded.

References: [Three.js KTX2Loader](https://threejs.org/docs/pages/KTX2Loader.html),
[Three.js GLTFLoader](https://threejs.org/docs/pages/GLTFLoader.html).
