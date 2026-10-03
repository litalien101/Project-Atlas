# Server and Authoritative-State TODOs

Scope: authored Python server modules and Python tests. The server audit
confirmed this application is documented as a loopback-only prototype, not a
public-network or account system. Keep that boundary explicit while fixing the
correctness defects.

## Priority fixes

The P1 correctness findings below should be fixed before relying on the
affected gameplay/rebuild behavior. They can proceed in parallel with offline
character generation; neither is a prerequisite for the CPU mesh pipeline.
Session-origin checks are relevant to the current local browser/server
workflow. Authenticated creator/reviewer identity is a gate for broader
deployment, not a requirement for local single-creator geometry authoring.
P1/P2 are server-surface risk labels, not a project-wide sequence.

### [`atlas_server/server.py`](../../atlas_server/server.py)

- **P1 — Reject client-forged server-only action data.** The action endpoint
  passes arbitrary object fields to the store. `_attack_origin` is trusted by
  attack resolution when present; a forged value was confirmed to allow an
  out-of-range attack. Reject reserved fields at the HTTP boundary and pass
  trusted rewind context separately. Validate again in the store.
  **Accept when:** forged attack attempts create no event or state change;
  valid server-resolved rewind still succeeds; all action types reject
  reserved/unknown fields.
- **P2 — Protect session-seat creation from foreign origins.** Apply the local
  host/origin policy to `POST /api/session`.
  **Accept when:** rejected cross-origin calls consume no seats; valid local
  clients retain the documented capacity response.
- **Deployment gate — Authenticate creator writes.** Entity and
  relationship write routes currently rely on the loopback boundary and do
  not identify an authenticated creator.
  **Accept when:** non-loopback deployment cannot enable these routes without
  an authenticated capability and authorization tests.
- **Keep existing controls:** retain loopback-only bind, authenticated
  session-bound gameplay identity, request-size limits, and security headers.
  These are prototype controls, not public-network authentication.

### [`atlas_server/store.py`](../../atlas_server/store.py)

- **P1 — Rebuild projections from clean baselines.** `rebuild_projection()`
  currently replays events into previously reduced personal player state.
  Repeated rebuilds were confirmed to increase gathered inventory from 1 to 2
  to 3; other replayed effects and saved ticks can likewise diverge.
  **Accept when:** rebuild starts event-derived state/ticks from a declared
  clean baseline and separates persistent non-event profile data; repeated
  rebuilds match the original projection for inventory, health, journal,
  combat, and ticks.
- **P2 — Make disconnect state replayable.** Session release currently writes
  stopped velocity directly to the projection without a corresponding event.
  **Accept when:** release/disconnect semantics are represented in the event
  source of truth and replay reproduces stopped movement.
- **P2 — Bound simulation replay and lock duration.** Avoid replaying the full
  history while holding the command write lock.
  **Accept when:** documented history caps/checkpoints bound work, and a
  concurrent gameplay test shows simulation cannot stall writes beyond its
  latency budget.
- **P2 — Resolve gameplay source IDs to durable command provenance.**
  **Accept when:** a source identifier either resolves to an authorized
  durable record or is rejected; dangling IDs cannot be presented as evidence.
- **Deployment gate — Replace traveler token as reviewer identity.**
  Define authenticated reviewer roles and self-review policy.
  **Accept when:** reviewer identity and authorization are server-verified,
  immutable in the audit record, and tested for unauthorized/self-review
  attempts.

### [`atlas_server/world.py`](../../atlas_server/world.py),
[`atlas_server/contracts.py`](../../atlas_server/contracts.py)

- **P2 — Validate event-specific payloads.** Check event type and payload
  against versioned schemas at commit and replay/import boundaries.
  **Accept when:** missing, malformed, extra, and unsupported fields/types are
  rejected consistently, and valid historical records replay.
- **Keep product claims bounded.** Mara and reed/beacon progression are
  scripted prototype systems; do not call them persistent autonomous NPC
  cognition or a connected economy. The world model must not trust client
  action metadata as authoritative context.

### [`atlas_server/policy.py`](../../atlas_server/policy.py)

- **P2 — Fail closed on malformed simulation input.** Reject NaN/infinities,
  booleans where integers are required, fractional/out-of-range costs, and
  invalid nested fields.
  **Accept when:** invalid values cannot bypass policy comparisons, with
  explicit validation errors and regression tests.

### [`atlas_server/character_profile.py`](../../atlas_server/character_profile.py)

- **P2 — Align stored appearance with reviewed runtime assets.** Current
  female-base-specific profile fields do not match the current no-registered-
  model status. Disable unsupported fields or migrate to versioned references
  validated against the asset manifest. Define retention/minimization before
  account-backed play.
  **Accept when:** unregistered assets/variants are rejected; migration and
  persistence behavior are tested.

## Per-file disposition

### `atlas_server/`

- [`__init__.py`](../../atlas_server/__init__.py) — No actionable issue found
  in this pass; package initializer is appropriately minimal.
- [`__main__.py`](../../atlas_server/__main__.py) — No actionable issue found
  in this pass; delegates to the server entry point.
- [`analytics.py`](../../atlas_server/analytics.py) — Add malformed event
  payload and unexpected event type coverage, coordinated with event contract
  validation. Existing observed-event summaries and retention limits are
  explicit.
- [`character_profile.py`](../../atlas_server/character_profile.py) — P2
  profile/asset-contract migration above; add dedicated appearance validation,
  persistence, and migration tests.
- [`contracts.py`](../../atlas_server/contracts.py) — P2 event-specific
  schema enforcement above; cover required/invalid/extra fields and unsupported
  event types.
- [`decision.py`](../../atlas_server/decision.py) — No actionable issue found
  in this pass; preserves the separation between human approval and deployment.
  Add malformed-decision-record tests if validation expands.
- [`history.py`](../../atlas_server/history.py) — No actionable issue found
  in this pass; bounded rewind history and sample validation have focused
  tests.
- [`policy.py`](../../atlas_server/policy.py) — P2 fail-closed numeric and
  nested-input validation above.
- [`reasoning.py`](../../atlas_server/reasoning.py) — Add direct tests for
  absent/invalid provenance records; current output distinguishes authored
  facts from inference.
- [`server.py`](../../atlas_server/server.py) — P1/P2 fixes above.
- [`simulation.py`](../../atlas_server/simulation.py) — Keep recorded-resource
  counterfactual distinct from behavioral forecasting or a market simulation.
  Future economy work needs transaction/accounting contracts and replayable
  market events; add malformed historical-event tests with contract validation.
- [`store.py`](../../atlas_server/store.py) — P1/P2 fixes above.
- [`world.py`](../../atlas_server/world.py) — Keep scripted Mara and
  reed/beacon progression distinct from persistent agent/economy features; add
  action/event payload validation coverage.

### `tests/`

- [`test_analytics.py`](../../tests/test_analytics.py) — Add malformed payload
  and unsupported event type cases.
- [`test_character_topology.py`](../../tests/test_character_topology.py) —
  No server-specific gap found in this pass; see character pipeline report.
- [`test_networking.py`](../../tests/test_networking.py) — Add forged internal
  action fields, exact repeated-rebuild equality, and release-then-rebuild
  regressions. Existing movement, retry, ownership, graph persistence, and
  rewind coverage remains useful.
- [`test_policy.py`](../../tests/test_policy.py) — Add NaN, infinity,
  bool-as-integer, fractional/out-of-range cost, and malformed nested-input
  cases.
- [`test_sessions.py`](../../tests/test_sessions.py) — Add cross-origin session
  creation and creator-route authorization tests; when reviewer auth is
  implemented, cover roles and self-review. Existing required-session APIs,
  provenance writes, review persistence, and legacy migration are covered.

## Deferred product work

- Persistent NPC beliefs/memory and behavior are roadmap work, not a defect in
  the current documented scripted prototype. Future acceptance requires
  evidence-grounded decisions, replayable state, and authoritative action
  validation.
- A real economy is roadmap work. Before claiming one, test atomic trades,
  currency/inventory conservation, production constraints, route capacity,
  and deterministic event replay.
