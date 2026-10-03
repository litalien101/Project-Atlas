# Project, Documentation, and Contract TODOs

Scope: master vision and status, project guidance, authored specifications,
policy/schema contracts, asset registry, and release configuration. This report
does not treat planned capabilities as current defects; it calls out mismatches
or missing gates explicitly.

## Vision, claims, and project onboarding

### Project vision and status documents

See [`MASTER_FILE.md`](../../MASTER_FILE.md) for the documentation index,
[`VISION.md`](../../VISION.md) for project intent, and
[`STATUS.md`](../../STATUS.md) for implementation claims.

- **P2 — Keep implementation status evidence-linked.** The overall vision is
  directionally aligned with the project, and the status document identifies
  important unimplemented systems. Continue separating implemented prototype,
  candidate-only, and planned work; link each claimed capability to its active
  contract and test/evidence.
  **Accept when:** a reader can distinguish a working local prototype from
  persistent autonomous NPCs, a connected economy, complete character
  production, and public deployment without inferring these exist.
- **Resolved (2026-10-03) — Reconcile local player scope.** The world-model
  specification now describes the current two-player local session and keeps
  public shared-world concurrency out of scope.

### [`README.md`](../../README.md)

- **Resolved (2026-10-03) — Correct licensing language.** README now
  distinguishes third-party dependency notices from Atlas source licensing and
  asset-specific rights. Atlas source remains without a project license grant.
- **Resolved (2026-10-03) — Remove unsupported truth-model enforcement claim.**
  Active README/world-model documentation now states that derived-claim
  confidence validation is not implemented. The supplementary truth/confidence
  YAML under `Reference_Assets/` remains planning material and is not treated as
  an active executable contract.

## World, policy, and decision contracts

### Historical truth-model reference finding — resolved

The active README and world-model specification no longer claim that the
supplementary truth/confidence YAML is an enforced contract. The ontology's
`TruthRecord` entry is only a type declaration; no truth-model evaluator is
implemented. Revisit this only when derived-claim behavior enters active scope.

### Policy YAML/schema and policy prose

- **P2 — Make machine-readable policy enforce the guarantees claimed in prose.**
  The prose-level policy promises exceed the current YAML contract's
  specificity.
  **Accept when:** every enforceable promise has a versioned field, allowed
  values, default, evaluator, and positive/negative contract test; deferred
  promises are explicitly labelled non-enforced.

### Decision recommendation and human-review actions

- **P2 — Separate recommendation from authorization.** Clarify whether a
  policy decision recommends an action or authorizes its execution. A
  recommendation must not be interpreted as a completed human review.
  **Accept when:** request, recommendation, human decision, execution, and audit
  event have unambiguous states and an end-to-end test covers approval,
  rejection, timeout, and replay.

### [`specs/local-multiplayer.md`](../../specs/local-multiplayer.md)

- **P1 — Align scope with the two-seat local prototype and harden its limits.**
  State local-only binding, two-seat capacity, session lifetime, disconnect
  semantics, event/projection expectations, and explicit non-support for
  public accounts/networking consistently. A browser origin check is not
  authentication.
  **Accept when:** endpoint tests and runtime behavior satisfy every stated
  boundary, and master/README wording agrees.

### [`specs/reach-world-model.md`](../../specs/reach-world-model.md)

The scope now matches the two-seat local session contract. Recheck both
documents if local seat capacity changes.

### [`specs/atlas-decision-engine.yaml`](../../specs/atlas/specs/atlas-decision-engine.yaml)

- **P2 — Clarify recommendation versus review action.** `modify` and `schedule`
  are listed as outputs but not human-review actions.
  **Accept when:** output semantics, review states, and execution authorization
  are explicit and validation/tests follow the contract.

### [`specs/atlas-policy-engine.yaml`](../../specs/atlas/specs/atlas-policy-engine.yaml)

- **P2 — Align policy contract with README.** Risk, evidence minimums, and
  per-rule policies are claimed more specifically in README than the YAML
  contract currently defines.
  **Accept when:** contract fields and validators enforce each claim or the
  claim is narrowed; decision cases have positive and negative tests.

### [`specs/atlas-ontology.yaml`](../../specs/atlas/specs/atlas-ontology.yaml)

- No specific issue found in the reviewed contract. Re-review if ontology
  terms or event payload requirements change.

### [`specs/atlas-schema-registry.yaml`](../../specs/atlas/specs/atlas-schema-registry.yaml)

- No specific issue found in the reviewed contract. Keep schema versions and
  migrations synchronized with implemented validators.

## Character and asset specifications

### [`specs/atlas-character-technical-spec-v1.md`](../../specs/atlas-character-technical-spec-v1.md)

- **P2 — Keep no-current-runtime-asset status explicit.** This spec accurately
  notes that there is no registered character model. The appearance-save
  contract remains active for local persistence and retains body/equipment
  fields from the former female-base prototype; those fields are not backed by
  a currently registered model. Keep them labelled saved-only until a reviewed
  replacement model and versioned profile migration exist. Removed Mixamo
  clips must not be presented as current assets.
  **Accept when:** all runtime claims resolve to exact manifest entries and
  hashes, or are labelled removed/planned.
- **P2 — Tie each stage's approval to exact inputs.** Define scope-limited
  approvals for mesh, materials, markers, rig, weights, clips, and runtime
  registration, including stale-on-parent-change behavior.
  **Accept when:** a changed source hash invalidates only the dependent
  downstream approvals and release cannot accept a stale artifact.

### [`specs/atlas-clothing-authoring.md`](../../specs/atlas-clothing-authoring.md)

- **P2 — Keep clothing explicitly paused until a replacement base is approved.**
  The source-dependent preparation and registration scripts have been removed.
  Preserve the paused status and build new tools only for a reviewed base/rig
  contract.
  **Accept when:** no current workflow implies clothing tools are available;
  any replacement rejects stale base hashes and uses the approved rig contract.

### Observation, recipe, profile, and landmark contracts under [`specs/`](../../specs/)

- **Stage-gated — Version and separate evidence types before downstream
  intake/learning/release.** Keep source observations,
  creator profile, build recipe, build plan, marker/rig artifact, and runtime
  appearance as distinct contracts. Recipe output or generated candidates are
  not independent source observations.
  **Accept when:** contracts carry source/build lineage, rights evidence,
  units/axes, extraction method/version, confidence or uncertainty where
  applicable, and explicit schema migrations.
- **P2 — Close QA and provenance gaps.** Add reviewed-source provenance,
  topology/rig/deformation evidence, extraction warnings, and missing
  fingertip/marker confidence evidence where required by the stage.
  **Accept when:** incomplete or stale evidence cannot silently pass a later
  stage and validator tests cover missing, conflicting, and invalid values.
- **P2 — Ensure contract fields map to executed tools.** The model recipe
  contract contains UV, material, and texture requirements beyond the current
  implemented geometry tools.
  **Accept when:** unimplemented stages are visibly unsupported/planned and
  cannot appear complete merely because the document accepts those fields.

## Runtime assets, dependencies, and release controls

### [`web/assets/manifest.yaml`](../../web/assets/manifest.yaml)

- **Release gate — Make an empty registry an explicit non-release state.** The current
  manifest contains no registered runtime assets.
  **Accept when:** clients and release checks distinguish “no approved asset”
  from “asset loaded”; no absent character/art file is implied by fallback
  presentation.

### [`specs/visual-direction.md`](../../specs/visual-direction.md)

- **P2 — Add reviewable checks for objective visual requirements.** Retain
  subjective art review for qualities such as style and mood while defining
  evidence for measurable constraints.
  **Accept when:** reviewers can verify composition, readability,
  palette/accessibility, and supported-device constraints without claiming
  subjective quality is machine-verified.

### Runtime manifest and candidate/release workflow

- **Release gate — Require a non-empty, validated, rights-cleared release manifest.**
  Check artifact IDs, file existence, content hashes, compatibility, licenses,
  provenance, stage approvals, and size/performance budgets before release.
  **Accept when:** CI fails on missing/stale/mismatched entries and produces an
  auditable release report; candidate-only files never register automatically.

### Build/dependency configuration and workflow files

- [`package.json`](../../package.json) — No specific issue found in the
  reviewed scripts and dependencies.
- [`package-lock.json`](../../package-lock.json) — No specific issue found in
  inspected metadata.
- [`requirements.txt`](../../requirements.txt) — No specific issue found;
  reproducible dependency pinning is a release-hardening option, not a current
  defect.
- [`AGENTS.md`](../../AGENTS.md) — No specific issue found.
- [`.github/workflows/network-tests.yml`](../../.github/workflows/network-tests.yml)
  — Consider least-privilege permissions, explicit timeout and concurrency
  settings. CI is not a deployment/release gate.
- **P2 — Keep development checks reproducible.** Document clean-install/test
  commands and ensure CI runs maintained source tests and validation scripts.
  **Accept when:** clean CI reproduces supported development checks and
  failure reporting identifies the relevant artifact/contract.
- **P2 — Add an explicit pre-release operational checklist.** Cover migration
  strategy, backup/restore, observability, rate/abuse controls, incident
  response, rollback, ownership, and data retention before any move beyond
  loopback development.
  **Accept when:** release is blocked until each control has an owner, evidence,
  and tested procedure.

## Audit disposition

The remaining authored docs, schemas, configuration, and workflow files in the
reviewed scope had no additional standalone defect recorded in this pass beyond
the contract and cross-document issues above. Re-review them when contracts or
release scope change; absence of a finding is not certification.
