# Preliminary Stone Troll geometry review

Status: **review required; not accepted**.

Source candidate: `character_base_preview.glb`
SHA-256: `5c000b62ac5b11657f24bb238d300a759069da09ef89a3751f77bb9f4e28297b`

The adjacent front, side, back, and three-quarter PNGs were rendered from the saved `.blend` in Blender 5.2.2 using the workbench renderer, neutral review lighting, and `--gpu-backend vulkan`. The default OpenGL backend emitted `EGL_BAD_MATCH` warnings in headless mode; Vulkan completed the same render without EGL warnings or errors. They are candidate-review views, not design approval.

## Preliminary observations

- The candidate is a complete upright T-pose blockout with broad horizontal arms, separate legs, feet, head, horns, ears, and facial feature geometry.
- The front silhouette is strongly simplified. The waist narrows sharply below the chest; the head is small relative to the body and the arms read as long and straight.
- Hands appear as rounded masses with small protrusions; individual fingers and thumb separation are not clearly legible at this scale. Inspect close views before considering the T-pose complete.
- From the side, the shoulder/upper-arm transition has a pronounced round bulge. Check whether it is intended anatomy or an artifact of the current metaball forms.
- The horns read upright in front view; the profile's swept-back horn description is not clearly expressed. Ears are broad triangular forms. Both need design review.
- These are preliminary observations, not a design acceptance decision. No approved target reference or exemplar was available, so design fidelity cannot be scored.

The candidate remains `blockout_only`. Do not advance it to rigging based on this note.
