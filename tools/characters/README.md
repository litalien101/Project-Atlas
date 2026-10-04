# Character Tools

The current authoring path is Recipe Studio → validated profile → compiled
recipe → frozen build plan → Blender blockout → human review. Start the local
workbench with `python3 tools/characters/recipe_studio_server.py`. It binds to
loopback and does not call a remote service.

The committed neutral profile is a technical starting point, not a designed
character. Replace its brief and values with an approved design before using it
as a candidate target. The deterministic parser maps explicit supported
measurements only. Blender emits `blockout_only` geometry; it does not provide
production topology, final materials, rigging, weights, or animation.

For reference intake, `inspect_character_source.py` creates hash-pinned
technical records and an unknown-by-default observation draft from upright
humanoid `.blend`, `.glb`, and `.gltf` sources. Its screening report is
technical triage only. It does not decide rights, visual quality, source
lineage, anatomy labels, learning eligibility, or runtime approval.

See [`../../specs/atlas-character-generation.md`](../../specs/atlas-character-generation.md),
[`../../art/characters/recipe_observations/README.md`](../../art/characters/recipe_observations/README.md),
and [`../../specs/source-model-intake-lifecycle.md`](../../specs/source-model-intake-lifecycle.md).
