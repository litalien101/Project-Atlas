# The Reach world model

## Contract source

The authoritative entity and relationship contracts live in:

- `../../specs/atlas/specs/atlas-ontology.yaml`
- `../../specs/atlas/specs/atlas-schema-registry.yaml`

`atlas_server.contracts.AtlasContracts` loads these files with PyYAML `safe_load()` during startup. Startup stops if the registered ontology is inconsistent or if any seeded entity or relationship fails validation. Every accepted action is validated as a registered `Event` entity before the SQLite transaction commits.

## Game concepts

| Reach concept | Atlas entity type | Stable identifier |
| --- | --- | --- |
| Wayfarer | `Player` | `9163de5b-b156-5d5e-bb43-f371650c4998` |
| World author | `Creator` | `3ec83798-e816-5d19-87ba-25b3d93c504f` |
| Valley of First Light | `Region` | `55cab3bc-32ce-5db6-b831-3dbde118912e` |
| Mara the Wayfinder | `NPC` | `a237cd4e-50fb-5448-9f16-88c6a2436d3e` |
| Listening Beacon | `Building` | `b71e10e4-cb79-5c1e-9355-542c1d82512d` |
| Mossling | `Creature` | `a4e5a9ad-2176-52b4-a130-aeafcdbef021` |
| Lumen reed patches | `ResourceNode` | One stable UUID per patch in `atlas_server/world.py` |

Each seeded entity has a UUID, registered type, and timezone-aware `created_at`. Seeded relationships are validated at startup:

- Player and Mara `located_in` the Valley.
- Beacon and each ResourceNode `placed_in` the Valley.
- Mossling `located_in` the Valley.

## Action event contracts

| Event type | Ontology relationship | Subject | Object |
| --- | --- | --- | --- |
| `PlayerMoved` | No graph edge; the event payload records the authoritative horizontal position and velocity, height, vertical velocity, grounded state, and movement tick | Player | None |
| `ResourceGathered` | `gathers` | Player | ResourceNode |
| `NPCSpokenTo` | `speaks_with` | Player | NPC |
| `BeaconAwakened` | `awakens` | Player | Building |
| `CreatureDamaged` | `attacks` | Player | Creature |

Events store a schema version, UTC occurrence time, actor UUID, player-action source UUID, rationale, affected entity IDs, and deterministic payload. They are creator/player-authored history, not AI-derived `TruthRecord` claims. The current save projection is rebuildable from the ordered event log.

## Persistent knowledge and memory

`atlas_entities` and `knowledge_relationships` persist the ontology-validated world model in SQLite. Startup idempotently seeds the curated reference-world entities and baseline relationships. Gameplay actions append event-backed graph edges in the same transaction as the event and state projection. Creator edits use `EntityCreated` and `RelationshipEstablished` events; the actor is the registered `Creator` entity, and each write records its source reference and authored rationale.

The local authoring endpoints are `POST /api/entities` and `POST /api/relationships`. Query `GET /api/knowledge` to retrieve graph edges with source and target entities plus event provenance, or `GET /api/memory` to page through immutable events by sequence and entity. Both reads require a local traveler session. See the README for request shapes. These are prototype loopback interfaces, not remote account or creator services.

`GET /api/analytics` computes deterministic counts from a cursor-bounded page of world events: event and actor activity, daily activity, resource flow, social interactions, progression milestones, and combat results. It reports observed counts only. The reference world has no durable account identity, so it cannot measure retention; the analytics output also makes no root-cause or causal claims.

`GET /api/reasoning?event=<uuid>` provides a provenance trace of one immutable event and its related entities/relationship. It reports the author's rationale and stored result as evidence; it does not assign inferred confidence or assert causality. Derived `TruthRecord` claims remain subject to the separate two-source, 0.80-confidence validation gate.

## Scope

This mapping covers one local player in one fixed region. It does not define account identity, shared-world concurrency, combat, inventory item entities, claim confidence, or AI-authored facts. Add concepts to the canonical ontology and registry before introducing them into the game server.
