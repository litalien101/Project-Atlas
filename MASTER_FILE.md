# Project Atlas Documentation Index

This file is the navigation and document-ownership index for Project Atlas. It
replaces the former all-in-one master file. Read the focused documents below
for the current vision, architecture, implementation status, roadmap, and
decisions. Detailed subsystem specifications remain authoritative for their
own contracts and workflows.

## Start here

- [`README.md`](README.md) — project overview, local setup, and running the
  current prototype.
- [`AGENTS.md`](AGENTS.md) — contributor guidance, repository map, and change
  rules.
- `.github/copilot-instructions.md` and `/srv/current_status/README.md` —
  assistant-specific guidance and the local live coordination protocol for
  shared file and contract ownership. The latter is outside Git and is not a
  project source-of-truth document.
- [`VISION.md`](VISION.md) — intended player experience, core gameplay loop,
  project goals, principles, and system map.
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — subsystem design and how the planned
  asset, learning, world, NPC, and economy systems fit together.
- [`STATUS.md`](STATUS.md) — what exists now, what is partial, and what is not
  implemented.
- [`ROADMAP.md`](ROADMAP.md) — staged work and intended sequencing.
- [`DECISIONS.md`](DECISIONS.md) — durable design decisions and their rationale.
- [`CHANGELOG.md`](CHANGELOG.md) — dated historical notes about changes and
  verification.
- [`to_do.md`](to_do.md) — detailed actionable checklist for the character
  asset-authoring pipeline.

## Detailed specifications

The subsystem documents below own their technical contracts. Update them when
changing their schemas, commands, behavior, or review gates; update `STATUS.md`
when implementation state changes and `CHANGELOG.md` with a dated summary.

- [`specs/atlas-character-generation.md`](specs/atlas-character-generation.md)
  — character profile, recipes, geometry generation, review, and marker flow.
- [`specs/atlas-model-recipe-v1.schema.json`](specs/atlas-model-recipe-v1.schema.json)
  — cross-category model-recipe data contract.
- [`specs/atlas-character-observation-v1.schema.json`](specs/atlas-character-observation-v1.schema.json)
  and [`art/characters/recipe_observations/README.md`](art/characters/recipe_observations/README.md)
  — observation evidence and review workflow.
- [`specs/source-model-intake-lifecycle.md`](specs/source-model-intake-lifecycle.md)
  — handoff from source acquisition and rights review through intake, observation,
  learning, build, and runtime release.
- [`specs/atlas-character-technical-spec-v1.md`](specs/atlas-character-technical-spec-v1.md)
  — runtime character, rig, customization, and equipment contracts.
- [`specs/reach-world-model.md`](specs/reach-world-model.md) — world entities,
  event history, knowledge, memory, and reasoning.
- [`specs/asset-provenance.md`](specs/asset-provenance.md) and
  [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) — rights, attribution, and
  redistribution rules.
- [`art/characters/sources/README.md`](art/characters/sources/README.md) —
  character reference sources, checksums, licenses, and limitations.

## Workspace asset references outside this repository

These inventories are local workspace material, not Git-tracked project
contracts. They document candidate sources; Project Atlas's indexed workflows
and release rules remain authoritative for use in the application.

- `/srv/source_models/README.md` and `/srv/source_models/AUDIT.md` — local
  source-model catalog, quality dispositions, and dated review. These paths
  exist in the workspace and are outside this Git repository; they are not
  repository-relative links on GitHub.
- `/srv/projects/Reference_Assets/README.md` — retained reference assets and
  planning archive. Its planning material is explicitly non-authoritative for
  current implementation status and is maintained outside this repository.

## Document ownership and update rules

Each subject has one authoritative home:

| Subject | Owner | Update it when |
| --- | --- | --- |
| Player promise and intended experience | [`VISION.md`](VISION.md) | The intended player experience, core loop, or project principles change. |
| System boundaries and subsystem design | [`ARCHITECTURE.md`](ARCHITECTURE.md) | A subsystem's intended responsibilities or relationships change. Detailed contracts belong in its specification. |
| Implemented versus planned capability | [`STATUS.md`](STATUS.md) | Code, data, or accepted assets materially change what works. Describe observed behavior; don't infer capability from a plan or schema. |
| Work sequence and milestones | [`ROADMAP.md`](ROADMAP.md) | Priorities, dependencies, or planned phases change. Keep checkboxes and milestones actionable and current. |
| Durable choices and rationale | [`DECISIONS.md`](DECISIONS.md) | A decision is adopted, superseded, or needs its rationale clarified. Link to implementation/specification details instead of copying them. |
| Historical change record | [`CHANGELOG.md`](CHANGELOG.md) | A meaningful change is completed. Add a dated factual note with affected files and verification performed. It is history, not the current specification. |
| Detailed behavior, schema, and workflow | The relevant file in [`specs/`](specs/) or subsystem documentation | A contract or workflow changes. Keep examples and validators aligned with actual implementation. |
| Character pipeline tasks | [`to_do.md`](to_do.md) | Character authoring work is added, completed, or re-sequenced. |
| Setup and run instructions | [`README.md`](README.md) | A user-facing command, dependency, or entry point changes. |
| Live parallel-work claims and handoffs | `/srv/current_status/atlas_coord.sqlite3` (local, outside Git) | An AI/human task starts, changes scope/status, waits, resumes, or completes. Use `python3 /srv/current_status/atlas_coord.py show`; the CLI and protocol are in `/srv/current_status/README.md`. Legacy JSON files are snapshots, not live state. |

When a change affects multiple subjects, update each owning document and add
cross-links. Do not maintain competing copies of the same detailed contract.
The index should stay concise and point to owners rather than restating their
contents. Clearly label proposals and plans; only mark something implemented
when the code or reviewed asset supports that claim. Record verification
actually performed, and do not imply a test suite ran when it did not.

## Maintenance

Keep links relative to this directory. Before finishing documentation changes,
check for stale references to the former monolithic file, broken local links,
and contradictory implementation claims. Do not split or merge these documents
again without updating this ownership table and the contributor instructions.
