# Project Atlas Copilot instructions

Before changing project files, read these in order:

1. `/srv/current_status/README.md`
2. `python3 /srv/current_status/atlas_coord.py show` (live state is stored in
   `/srv/current_status/atlas_coord.sqlite3`; the legacy JSON is a snapshot)
3. `/srv/projects/Project_Atlas/AGENTS.md`
4. `MASTER_FILE.md`, then the authoritative documents for the task's subsystem.

Register each active task with `/srv/current_status/atlas_coord.py claim`
before editing. Include purpose, context, next milestone, branch/base commit,
exact file scopes, and semantic contract IDs. Check `git status --short
--branch` and `git log -1 --oneline` first; preserve existing uncommitted work.
Do not edit a path or contract held by another active task. If overlap is
reported, mark the task waiting or narrow it to independent work. Re-read the
changed files and Git state after resuming. Keep timestamps, context, next
action, and blockers current; heartbeat active and waiting work at least every
90 minutes. Mark completed work complete to release its claims.

Contract IDs represent stable semantics, not a schema version or a particular
file. Claim them when changing shared model fields, API shapes, event meaning,
persistence formats, identifiers, or invariants. Use consistent namespaced IDs
such as `game.PlayerProfile` or `world.WorldState`, even when multiple systems
implement or consume the concept. Do not add a version suffix to evade a
conflict. If the affected contracts are not yet known, claim with
`--contracts-unknown`, investigate, and replace that broad scope with exact
contract IDs promptly. Contract ownership supplements file ownership and does
not replace compatibility review.

Work professionally and follow current engineering practices: make small,
reviewable changes; follow existing architecture, types, style, and versioned
contracts; preserve authorization, provenance, rights, and release gates; and
avoid unrelated refactors or duplicate sources of truth. Do not claim planned
functionality exists until implemented. Run relevant targeted checks and say
exactly what ran and what remains unverified.

Update the authoritative documentation identified by `MASTER_FILE.md` whenever
implementation, behavior, status, roadmap, or decisions change. Add a dated
`CHANGELOG.md` entry with affected files and actual verification. Keep docs
concise and link to their single owner rather than copying long sections.
Review `git diff` and `git status` before handoff. Do not discard, stage, commit,
push, merge, or switch branches over another contributor's work. Commit or
publish only when authorized by the project owner or standing instructions.
