# Character build failure records

This directory keeps compact, machine-readable lessons from failed or
superseded character builds. It preserves each original `build.json` manifest,
recipe, artifact size, SHA-256, failure evidence, and a prevention rule. The
large `.blend` and `.glb` outputs are removed after their hashes are verified;
the record is sufficient to diagnose the attempt without leaving stale models
in the candidate area.

Records are negative evidence, not approved assets or automatic training data.
Promote a lesson into a generator guardrail only when the failure has a
reproducible cause. The MPFB prototype's current guardrails reject combined
outfit fields, cap runtime texture dimensions, and hide the armature behind the
mesh. Blender's GLB importer independently defaults imported armatures to
"In Front"; the dedicated inspection-file tool disables that Blender-only
overlay. Keep new failure codes specific and tie each rule to recorded evidence.

See [`mpfb_prototype_attempts.json`](mpfb_prototype_attempts.json) for the
initial cleanup record. The current candidate remains under
`art/characters/pending_models/` and still requires normal review.
