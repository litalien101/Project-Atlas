# Character recipe observations

This folder is reserved for one versioned observation per independent,
rights-reviewed character source. Files must conform to
[`atlas-character-observation-v1.schema.json`](../../../specs/atlas-character-observation-v1.schema.json).

## What belongs here

Each observation records canonical features, optional normalized measurements,
explicit structural relationships, source/license details, derivation lineage,
and human review status. Use stable concept IDs rather than free-form synonyms.
Record `present`, `absent`, and `unknown` separately; a feature omitted from a
description is not evidence that the feature is absent.

Only reviewed observations with `rights_status: cleared_for_analysis` should
contribute to recipe-mining statistics. Do not count multiple poses, renders,
or derivative meshes from the same original as independent examples. Keep
draft extractions traceable so a reviewer can correct or reject them.

## Relationship learning

The future local miner will find co-occurrence and typed graph patterns across
these observations. It must report the number of independent examples and
eligible denominator, uncertainty, context, exclusions, source IDs, and input
hashes. A mined pattern is a candidate, not a character rule. Human-reviewed
findings may later be promoted into the authored grammar, where they can inform
new recipes as optional, explainable suggestions.

No observation dataset is approved yet. Do not add inferred population rules
or claim the system has learned a pattern until the observation data, miner,
and review process exist.

## Observation versus build recipe

An observation is evidence about a source asset. A build recipe is an
instruction record for a specific reproducible candidate. The cross-category
build contract is documented in
[`atlas-model-recipe-v1.schema.json`](../../../specs/atlas-model-recipe-v1.schema.json).
It can capture dimensions and frames, parameter values and influence weights,
geometry/topology settings, materials and texture hashes, component transforms
and links, UV policy and material assignments, rig, animation and skin-weight
references, variants, collision, LOD/performance limits, validation evidence,
and output checksums. It does not contain the
actual mesh or per-vertex skin arrays; those remain binary asset data or
referenced sidecars. The schema is not wired into a builder yet.
