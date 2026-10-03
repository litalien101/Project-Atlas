# Project Atlas Roadmap

## Roadmap

## Parallel current gameplay integrity work

These confirmed findings were identified in the implementation audit and do
not block offline geometry work. Keep them visible while the first character
target is reviewed:

- [ ] Reject client-forged server-only action context and prove rejected
  requests do not mutate state or events.
- [ ] Make event projection rebuilds idempotent from declared clean baselines.
- [ ] Apply the intended loopback origin/host checks to local session creation.

The detailed findings and acceptance notes remain in
[`project_audit/server/TODO.md`](project_audit/server/TODO.md). The audit is a
dated snapshot; verify each issue against current code before implementation.

### Phase A — Stop bad outputs being treated as finished

**Status: safeguards, a recipe-driven blockout path, and a reviewed-source
adaptation path are implemented; the target geometry milestone remains open.**
The milestone is a reviewed geometry-only Stone Troll in a complete T-pose. It
does not require final textures, surface detailing, or a rig. The previous
browser base was removed during a rights audit; no accepted runtime character
mesh is registered.

### Phase B — Stabilize model authoring

- Select a modeling strategy that produces the requested design at useful
  detail: a reviewed authored mesh/sculpt, a validated geometry source, or a
  deterministic generator with enough shape and topology control.
- Validate dimensions, connected body regions, boundaries, normals, materials,
  and source rights before acceptance.
- Add repeatable deformation previews for shoulders, elbows, wrists, hips, and
  knees once a valid rig is available.
- Build a creator-facing, multi-view marker UI with draggable Mixamo-style
  anchors, then generate the skeleton from the reviewed marker artifact using a
  versioned rig template. Keep skin weights and deformation review as separate
  gates.
- Record visual-review cases, target device budgets, and why a candidate passes
  or fails.
- Generalize shared asset intake, recipe/version records, provenance, QA, and
  runtime registration beyond characters; keep per-category generators and
  validators appropriate to their geometry and use.
- Define an evidence-backed feedback loop for failed and successful asset
  trials, with review before learned changes alter an approved recipe.
- After the character stage contracts and command behavior stabilize, evaluate
  a unified `atlas character` CLI for inspect, screen, compile, build, review,
  and export. Keep the current Python tools as the implementation layer unless
  a tested facade provides clear workflow value; do not add a wrapper class
  solely to reduce the visible script count.

### Phase C — Collect normalized recipe evidence

- Define and version canonical trait, anatomy-region, material, and relation
  vocabularies.
- Add one observation per independent reference, with rights and lineage.
- Separate observed presence, explicit absence, unknown, and not applicable.
- Review extracted attributes before they enter the dataset.

### Phase D — Discover and review patterns

- Implement a deterministic local miner for co-occurrence and typed graph
  relationships.
- Stratify results by archetype, style, function, source quality, and other
  relevant context; avoid mixing incompatible groups.
- Report sample support, denominators, uncertainty, provenance, and data hash.
- Evaluate findings on held-out examples and compare against simple baselines.
- Keep findings as candidates until a reviewer approves a versioned rule.

### Phase E — Compose and evaluate new recipes

- Let the compiler use approved rules as weighted suggestions and compatible
  combinations, not mandatory stereotypes.
- Preserve user-specified requirements and allow explicit exceptions.
- Explain which evidence influenced every generated recipe.
- Feed reviewed outcomes back as new observations without treating generated
  variations as independent source evidence.

### Phase F — Stateful NPCs

- Define versioned personality, needs, goals, emotion, memory, belief, and
  relationship contracts.
- Implement local scheduled agent decisions with limited knowledge, explicit
  action policies, and event-sourced outcomes.
- Let player/NPC and NPC/NPC interactions update social relationships with
  evidence and context.
- Evaluate consistency, memory retrieval, relationship changes, bounded
  behavior, and replay determinism before increasing population size.
- Keep dialogue generation separate from authoritative decisions and world
  writes.

### Phase G — Connected regional economy

- Define goods, inventories, producers, consumers, markets, money flows,
  settlements, routes, and institutions as versioned world contracts.
- Build a small local-market simulation first, then connect neighboring
  markets through delayed, capacity-limited routes.
- Add conservation and accounting invariants, policy review, explainable
  counterfactuals, and creator-controlled deployment.
- Let agents participate using their own knowledge, resources, roles, and
  incentives; do not let agents bypass market accounting.

### Phase H — Persistent world operation

- Add durable identities, secure accounts, presence, reconnect behavior, and
  server-driven multiplayer scheduling before exposing sessions remotely.
- Scale NPC and economy update cadence with explicit simulation budgets and
  interest/region scheduling.
- Add operations, backups, migrations, observability, abuse controls, and
  rollback before public deployment.

### Phase I — State-responsive character appearance

- Version the character appearance state separately from identity and base
  asset data.
- Define species-specific aging and prolonged-stress rules, including timing,
  thresholds, persistence, and supported variants.
- Build hair, material, and morph options for supported changes such as gradual
  greying; validate combinations with customization, animation, and lighting.
- Let simulation events update appearance state through explicit rules, then
  resolve to registered runtime assets without generating geometry on every
  frame.
