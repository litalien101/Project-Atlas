# Character build failure records

This directory keeps compact, machine-readable lessons from failed or
superseded character builds. It preserves each original `build.json` manifest,
recipe, artifact size, SHA-256, failure evidence, and a prevention rule under
`manifests/` and in `mpfb_prototype_attempts.json`. The large `.blend` and
`.glb` outputs are removed after their hashes are recorded; the metadata is
kept so failures can still be diagnosed without retaining stale models.

Records are negative evidence, not approved assets or automatic training data.
Promote a lesson into a generator guardrail only when the failure has a
reproducible cause. The MPFB prototype's current guardrails reject combined
outfit fields, cap runtime texture dimensions, force solid character materials
opaque, mask the body away from open garment edges, and fit the raised pants
inside the sweater at their overlap.
Blender's GLB importer defaults imported armatures to "In Front"; the dedicated
inspection file hides the armature bones in its default viewport while keeping
the rig available to unhide. Keep new failure codes specific and tie each rule
to recorded evidence.

See [`mpfb_prototype_attempts.json`](mpfb_prototype_attempts.json) for the
attempt history and preserved build manifests. Only the current regenerated
candidate belongs in `art/characters/exports/`; superseded model binaries are
removed after review while manifests and failure evidence remain archived.
