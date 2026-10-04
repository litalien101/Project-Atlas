# Local two-player session and tick model

## Scope

This milestone supports two travelers connected to one loopback server. It proves identity scoping, independent movement ticks, shared-world actions, and persistence across server restarts. It does not provide accounts, passwords, remote networking, or a security boundary between people who can access the local machine.

## Ownership

- The world projection owns shared terrain progress: gathered reed patches, Mara's shared introduction, beacon state, and Mossling health/defeat state.
- Each stable Player entity owns its position and velocity, inventory, health, defense stance, journal, and last acknowledged movement tick.
- Reed pickups and beacon offerings use the acting traveler's inventory. A reed patch can be gathered once by either traveler; the beacon and Mossling outcomes are shared.
- Each browser tab owns one short-lived opaque session token. The server assigns that token to the first available traveler seat and accepts it only while the server process is running.
- A session token is a local capability for routing requests. It is not an account credential and must never be treated as authentication for a network-accessible service.

## Request identity

`POST /api/session` assigns one of two seats and returns the token, player ID, and display name. The browser retains the token in `sessionStorage` for that tab. `GET /api/state` and `POST /api/action` require the token in `X-Atlas-Session`; player identity is resolved by the server, never accepted from an action body. Unknown tokens receive HTTP 401. A third concurrent session receives HTTP 409. Closing or navigating away from a tab posts `POST /api/session/close` to release its seat; abandoned sessions expire after 30 seconds without a request. Explicit close and idle expiration both record a `PlayerSessionReleased` event in the same SQLite transaction that persists zero velocity. Projection rebuild replays this event, so a stopped traveler does not resume stale movement. Player progress is already committed to SQLite with each accepted action, so session cleanup does not discard it. Restarting the loopback server also expires sessions without deleting saved player state.

## Tick and persistence rules

- Movement frame sequence is a per-player server tick. Player 1 and Player 2 may both submit tick 1; a player may not reuse another player's acknowledgement or history.
- A movement frame carries normalized horizontal input, run intent, and an edge-triggered jump press. The server advances horizontal and vertical movement at 60 Hz; grounded state, height, vertical velocity, jump buffering, and coyote time are stored with the owning player.
- A movement batch contains at most 32 contiguous ticks. Duplicate retries return that player's cached acknowledgement; stale or gapped batches are rejected.
- Action requests accept only fields declared for their action type. Server-only movement and attack context is never accepted from a request; an attack's optional `rewind_sequence` selects only a matching recent server-recorded sample.
- Player state and the shared world projection are committed in one SQLite transaction with the immutable event. Event actor and subject IDs identify the owning Player entity.
- The player's last tick is persisted with the player state. On a new session, the browser resumes at the acknowledged tick. Movement events record the tick so projection rebuild restores that acknowledgement. The retry cache and rewind window are process-local and empty after restart.
- Projection rebuild starts event-derived shared and player state and ticks from their declared defaults, then replays the immutable event log in sequence. Appearance profiles are stored in separate `player_profiles` rows and are not reset by replay.
- Legacy single-player saves migrate in place: the existing traveler remains Player 1 with their progress, while Player 2 receives a fresh profile. Shared world progress is preserved.

## Local play

Open the game in two separate browser tabs. Each tab claims an available traveler seat, renders both travelers, controls its own traveler, and polls authoritative snapshots for the other. Closing a tab releases its seat; idle sessions are cleaned up automatically. Saved progress remains in `data/world.sqlite3`.
