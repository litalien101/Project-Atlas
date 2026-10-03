# Character reference images

`stone_troll_front_clean.png` is the user-provided Bing Image Creator reference
from `/srv/projects/troll.jpg`, saved with a transparent background. The
foreground mask uses local color contrast and keeps the connected component
seeded from the torso to discard background and detached floor-shadow pixels.
The original character RGB pixels are preserved; only the alpha channel was
added.

The image is a silhouette guide for deterministic Blender fitting. It adjusts
the procedural blockout's front widths; it is not a production texture or a
source of hidden-side geometry. The review model and extracted measurements
are under `../pending_models/stone_troll/`.

`stone_troll_style_reference.jpeg` is the second user-provided image. It has a
useful troll design, but its arms are lowered and it includes a loincloth. The
current fitter reads width by height and assumes a front-facing T-pose, so this
image is retained as a visual style reference rather than used to drive the
current mesh fit.
