"""SQLite persistence for shared world history and per-player projections."""

from __future__ import annotations

import json
import secrets
import sqlite3
import time
import uuid
from threading import RLock
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import AtlasContracts
from .character_profile import DEFAULT_APPEARANCE, validate_appearance
from .analytics import summarize_events
from .simulation import run_simulation as simulate_recorded_events
from .policy import PolicyEngine
from .decision import generate_decision
from .history import EntityHistory, HitboxSnapshot
from .world import (
    CREATOR_ENTITY_ID, PLAYER_ENTITY_ID, PLAYER_ENTITY_IDS, PLAYER_NAMES, PLAYER_STARTS,
    WORLD_ENTITY_IDS, apply_action, initial_state, normalize_movement, replay_event,
)

PERSONAL_FIELDS = ("player", "inventory", "player_health", "player_defense", "journal")
SESSION_IDLE_TTL_SECONDS = 30.0
MAX_SIMULATION_EVENT_HISTORY = 10_000


ACTION_FIELDS = {
    "move": {"type", "sequence", "frames", "input", "run", "jump"},
    "attack": {"type", "target", "rewind_sequence"},
    "block": {"type", "target"},
    "dodge": {"type", "target"},
    "reawaken": {"type", "target"},
    "interact": {"type", "target"},
}
MOVEMENT_FRAME_FIELDS = {"sequence", "input", "run", "jump"}


def _validate_movement_input(value: Any) -> None:
    if isinstance(value, dict):
        if any(not isinstance(field, str) for field in value):
            raise ValueError("Movement input fields must be strings.")
        unsupported = value.keys() - {"x", "z"}
        if unsupported:
            raise ValueError(
                "Unsupported movement input field(s): "
                + ", ".join(sorted(unsupported))
                + "."
            )


def validate_action(action: Any) -> dict[str, Any]:
    """Reject client-only fields before action data can reach world rules."""
    if not isinstance(action, dict):
        raise ValueError("Action must be an object.")
    kind = action.get("type")
    if not isinstance(kind, str):
        raise ValueError("Action type must be a string.")
    allowed = ACTION_FIELDS.get(kind)
    if allowed is None:
        raise ValueError("That action is not available.")
    if any(not isinstance(field, str) for field in action):
        raise ValueError("Action fields must be strings.")
    unsupported = action.keys() - allowed
    if unsupported:
        raise ValueError(f"Unsupported action field(s): {', '.join(sorted(unsupported))}.")
    if kind == "move":
        _validate_movement_input(action.get("input"))
        frames = action.get("frames")
        if isinstance(frames, list):
            for frame in frames:
                if isinstance(frame, dict):
                    if any(not isinstance(field, str) for field in frame):
                        raise ValueError("Movement frame fields must be strings.")
                    unsupported_frame_fields = frame.keys() - MOVEMENT_FRAME_FIELDS
                    if unsupported_frame_fields:
                        raise ValueError(
                            "Unsupported movement frame field(s): "
                            + ", ".join(sorted(unsupported_frame_fields))
                            + "."
                        )
                    _validate_movement_input(frame.get("input"))
    return action


def _split_state(state: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    personal = {key: state[key] for key in PERSONAL_FIELDS if key in state}
    shared = {
        key: value for key, value in state.items()
        if key not in PERSONAL_FIELDS and key not in {"appearance", "players"}
    }
    return shared, personal


def _initial_player_projection(player_id: str) -> dict[str, Any]:
    state = initial_state()
    x, y = PLAYER_STARTS[player_id]
    state["player"].update(x=float(x), y=float(y))
    if player_id != PLAYER_ENTITY_ID:
        state["journal"] = ["Explore the valley together."]
    _, personal = _split_state(state)
    return personal


class WorldStore:
    """One shared valley, two durable traveler profiles, and ephemeral tab sessions."""

    def __init__(self, path: Path, contracts: AtlasContracts, policy_engine: PolicyEngine | None = None):
        self.path = path
        self.contracts = contracts
        self.policy_engine = policy_engine or PolicyEngine(
            Path(__file__).resolve().parents[1] / "specs" / "atlas" / "specs" / "atlas-policy-engine.yaml")
        self._command_lock = RLock()
        self._sessions: dict[str, str] = {}
        self._seat_by_player: dict[str, str] = {}
        self._session_last_seen: dict[str, float] = {}
        self._runtime: dict[str, dict[str, Any]] = {}
        self._target_history = EntityHistory(max_seconds=2.0, max_samples=120)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()
        for player_id in PLAYER_ENTITY_IDS:
            self._runtime[player_id] = self._make_runtime(self._last_tick_from_db(player_id))
        # Compatibility aliases used by the single-player movement tests and tools.
        self._player_history = self._runtime[PLAYER_ENTITY_ID]["history"]
        for player_id in PLAYER_ENTITY_IDS:
            state, _ = self.read(player_id)
            own = next(player for player in state["players"] if player["is_self"])
            self._record_history(player_id, own["last_processed_input"], time.monotonic(), state["player"])

    @staticmethod
    def _make_runtime(last_tick: int = 0) -> dict[str, Any]:
        return {
            "last_tick": last_tick,
            "active_input": {"x": 0.0, "z": 0.0},
            "active_run": False,
            "last_sim_tick": time.monotonic(),
            "sim_accumulator": 0.0,
            "ack_cache": {},
            "history": EntityHistory(max_seconds=2.0, max_samples=120),
        }

    def _record_history(self, player_id: str | int, sequence: int | float,
                        at: float | dict[str, Any], player: dict[str, Any] | None = None) -> None:
        if player is None:  # Preserve the original single-player test/helper signature.
            player = at
            at = sequence
            sequence = int(player_id)
            player_id = PLAYER_ENTITY_ID
        assert isinstance(player, dict)
        self._runtime[player_id]["history"].record(
            HitboxSnapshot(float(at), player["x"], 0.0, player["y"], .2, 1.8, 0.0, int(sequence))
        )
        self._target_history.record(HitboxSnapshot(float(at), 12.0, 0.0, 9.0, .35, 1.25, 0.0, int(sequence)))

    def connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("PRAGMA busy_timeout = 5000")
        return db

    def _initialize(self) -> None:
        with closing(self.connect()) as db:
            db.execute("PRAGMA journal_mode = WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS world_state (
                    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                    version INTEGER NOT NULL,
                    state_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS world_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    schema_version INTEGER NOT NULL,
                    occurred_at TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    source_kind TEXT NOT NULL,
                    source_identifier TEXT NOT NULL,
                    rationale TEXT NOT NULL,
                    subject_id TEXT NOT NULL,
                    object_id TEXT,
                    payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS player_states (
                    player_id TEXT PRIMARY KEY,
                    player_name TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    last_tick INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS player_profiles (
                    player_id TEXT PRIMARY KEY REFERENCES player_states(player_id),
                    appearance_json TEXT NOT NULL
                );
                CREATE TRIGGER IF NOT EXISTS world_events_no_update
                    BEFORE UPDATE ON world_events BEGIN SELECT RAISE(ABORT, 'events are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS world_events_no_delete
                    BEFORE DELETE ON world_events BEGIN SELECT RAISE(ABORT, 'events are immutable'); END;
                CREATE TABLE IF NOT EXISTS atlas_entities (
                    entity_id TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    attributes_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS knowledge_relationships (
                    relationship_id TEXT PRIMARY KEY,
                    relation_type TEXT NOT NULL,
                    source_entity_id TEXT NOT NULL REFERENCES atlas_entities(entity_id),
                    target_entity_id TEXT NOT NULL REFERENCES atlas_entities(entity_id),
                    recorded_at TEXT NOT NULL,
                    source_event_id TEXT UNIQUE REFERENCES world_events(event_id),
                    source_kind TEXT NOT NULL,
                    source_identifier TEXT NOT NULL,
                    rationale TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS simulation_runs (
                    simulation_id TEXT PRIMARY KEY,
                    model TEXT NOT NULL,
                    model_version TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    as_of_sequence INTEGER NOT NULL,
                    actor_id TEXT NOT NULL,
                    proposal_json TEXT NOT NULL,
                    result_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS policy_evaluations (
                    evaluation_id TEXT PRIMARY KEY,
                    simulation_id TEXT NOT NULL REFERENCES simulation_runs(simulation_id),
                    actor_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    result_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS atlas_decisions (
                    decision_id TEXT PRIMARY KEY,
                    simulation_id TEXT NOT NULL REFERENCES simulation_runs(simulation_id),
                    evaluation_id TEXT NOT NULL REFERENCES policy_evaluations(evaluation_id),
                    actor_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    result_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS decision_reviews (
                    review_id TEXT PRIMARY KEY,
                    decision_id TEXT NOT NULL UNIQUE REFERENCES atlas_decisions(decision_id),
                    reviewer_id TEXT NOT NULL,
                    action TEXT NOT NULL CHECK (action IN ('approve', 'reject', 'delay', 'escalate')),
                    rationale TEXT NOT NULL,
                    reviewed_at TEXT NOT NULL,
                    result_json TEXT NOT NULL
                );
                CREATE TRIGGER IF NOT EXISTS decision_reviews_no_update
                    BEFORE UPDATE ON decision_reviews BEGIN SELECT RAISE(ABORT, 'decision reviews are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS decision_reviews_no_delete
                    BEFORE DELETE ON decision_reviews BEGIN SELECT RAISE(ABORT, 'decision reviews are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS atlas_decisions_no_update
                    BEFORE UPDATE ON atlas_decisions BEGIN SELECT RAISE(ABORT, 'decisions are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS atlas_decisions_no_delete
                    BEFORE DELETE ON atlas_decisions BEGIN SELECT RAISE(ABORT, 'decisions are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS policy_evaluations_no_update
                    BEFORE UPDATE ON policy_evaluations BEGIN SELECT RAISE(ABORT, 'policy evaluations are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS policy_evaluations_no_delete
                    BEFORE DELETE ON policy_evaluations BEGIN SELECT RAISE(ABORT, 'policy evaluations are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS simulation_runs_no_update
                    BEFORE UPDATE ON simulation_runs BEGIN SELECT RAISE(ABORT, 'simulation runs are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS simulation_runs_no_delete
                    BEFORE DELETE ON simulation_runs BEGIN SELECT RAISE(ABORT, 'simulation runs are immutable'); END;
                CREATE INDEX IF NOT EXISTS knowledge_relationship_source_idx
                    ON knowledge_relationships(source_entity_id, relation_type, recorded_at);
                CREATE INDEX IF NOT EXISTS knowledge_relationship_target_idx
                    ON knowledge_relationships(target_entity_id, relation_type, recorded_at);
                CREATE UNIQUE INDEX IF NOT EXISTS knowledge_seed_edge_unique_idx
                    ON knowledge_relationships(relation_type, source_entity_id, target_entity_id)
                    WHERE source_event_id IS NULL;
                CREATE INDEX IF NOT EXISTS world_events_subject_time_idx
                    ON world_events(subject_id, occurred_at, sequence);
                CREATE INDEX IF NOT EXISTS world_events_object_time_idx
                    ON world_events(object_id, occurred_at, sequence);
                CREATE TRIGGER IF NOT EXISTS atlas_entities_no_update
                    BEFORE UPDATE ON atlas_entities BEGIN SELECT RAISE(ABORT, 'entities are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS atlas_entities_no_delete
                    BEFORE DELETE ON atlas_entities BEGIN SELECT RAISE(ABORT, 'entities are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS knowledge_relationships_no_update
                    BEFORE UPDATE ON knowledge_relationships BEGIN SELECT RAISE(ABORT, 'relationships are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS knowledge_relationships_no_delete
                    BEFORE DELETE ON knowledge_relationships BEGIN SELECT RAISE(ABORT, 'relationships are immutable'); END;
            """)
            db.execute(
                "INSERT OR IGNORE INTO world_state(singleton, version, state_json) VALUES (1, 0, ?)",
                (json.dumps(initial_state(), separators=(",", ":")),),
            )
            row = db.execute("SELECT state_json FROM world_state WHERE singleton = 1").fetchone()
            legacy_state = json.loads(row["state_json"])
            _, default_personal = _split_state(initial_state())
            default_appearance = initial_state()["appearance"]
            for player_id in PLAYER_ENTITY_IDS:
                exists = db.execute("SELECT state_json FROM player_states WHERE player_id = ?", (player_id,)).fetchone()
                existing_personal = json.loads(exists["state_json"]) if exists else None
                profile = db.execute(
                    "SELECT appearance_json FROM player_profiles WHERE player_id = ?", (player_id,)
                ).fetchone()
                if profile:
                    appearance = json.loads(profile["appearance_json"])
                elif existing_personal is not None:
                    appearance = existing_personal.get("appearance", default_appearance)
                elif player_id == PLAYER_ENTITY_ID:
                    appearance = legacy_state.get("appearance", default_appearance)
                else:
                    appearance = default_appearance
                if not isinstance(appearance, dict):
                    migrated_appearance = DEFAULT_APPEARANCE.copy()
                else:
                    candidate = {**DEFAULT_APPEARANCE,
                                 **{key: value for key, value in appearance.items()
                                    if key in DEFAULT_APPEARANCE}}
                    try:
                        migrated_appearance = validate_appearance(candidate)
                    except ValueError:
                        migrated_appearance = DEFAULT_APPEARANCE.copy()
                if profile:
                    if migrated_appearance != appearance:
                        db.execute(
                            "UPDATE player_profiles SET appearance_json = ? WHERE player_id = ?",
                            (json.dumps(migrated_appearance, separators=(",", ":")), player_id),
                        )
                elif exists:
                    db.execute(
                        "INSERT INTO player_profiles(player_id, appearance_json) VALUES (?, ?)",
                        (player_id, json.dumps(migrated_appearance, separators=(",", ":"))),
                    )
                if existing_personal is not None:
                    if "appearance" in existing_personal:
                        existing_personal.pop("appearance")
                        db.execute("UPDATE player_states SET state_json = ? WHERE player_id = ?",
                                   (json.dumps(existing_personal, separators=(",", ":")), player_id))
                    continue
                if player_id == PLAYER_ENTITY_ID:
                    personal = {key: legacy_state.get(key, value) for key, value in default_personal.items()}
                else:
                    personal = json.loads(json.dumps(default_personal))
                    x, y = PLAYER_STARTS[player_id]
                    personal["player"].update(x=float(x), y=float(y), vx=0.0, vz=0.0)
                    personal["journal"] = ["Explore the valley together."]
                db.execute(
                    "INSERT INTO player_states(player_id, player_name, state_json, last_tick) VALUES (?, ?, ?, 0)",
                    (player_id, PLAYER_NAMES[player_id], json.dumps(personal, separators=(",", ":"))),
                )
                db.execute(
                    "INSERT INTO player_profiles(player_id, appearance_json) VALUES (?, ?)",
                    (player_id, json.dumps(migrated_appearance, separators=(",", ":"))),
                )
            # Existing saves keep shared progress in the world row and player-specific
            # fields in player_states. This is an in-place migration from the old shape.
            shared, _ = _split_state(legacy_state)
            db.execute("UPDATE world_state SET state_json = ? WHERE singleton = 1",
                       (json.dumps(shared, separators=(",", ":")),))
            # Materialize the ontology-validated reference world as a durable graph.
            # Seed rows are immutable baseline facts; later edges must be backed by
            # an immutable world event and are inserted in the command transaction.
            db.execute("BEGIN IMMEDIATE")
            try:
                for entity in self.contracts.entity_by_id.values():
                    attributes = {key: value for key, value in entity.items()
                                  if key not in {"id", "type", "created_at"}}
                    db.execute(
                        """INSERT OR IGNORE INTO atlas_entities(
                               entity_id, entity_type, created_at, attributes_json
                           ) VALUES (?, ?, ?, ?)""",
                        (entity["id"], entity["type"], entity["created_at"],
                         json.dumps(attributes, separators=(",", ":"), sort_keys=True)),
                    )
                for relation in self.contracts.relationships_seeded:
                    relationship_id = str(uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        f"atlas:seed:{relation['type']}:{relation['source_id']}:{relation['target_id']}"))
                    db.execute(
                        """INSERT OR IGNORE INTO knowledge_relationships(
                               relationship_id, relation_type, source_entity_id,
                               target_entity_id, recorded_at, source_event_id,
                               source_kind, source_identifier, rationale
                           ) VALUES (?, ?, ?, ?, ?, NULL, 'world_manifest', ?, ?)""",
                        (relationship_id, relation["type"], relation["source_id"], relation["target_id"],
                         self.contracts.entity_by_id[relation["source_id"]]["created_at"],
                         relation["source_id"], "Declared by the curated reference-world manifest."),
                    )

                # Backfill relation edges for saves created before the graph tables.
                relation_by_event = {
                    "ResourceGathered": "gathers", "NPCSpokenTo": "speaks_with",
                    "BeaconAwakened": "awakens", "CreatureDamaged": "attacks",
                    "PlayerGuarded": "guards", "PlayerDodged": "evades",
                    "CreatureReawakened": "reawakens",
                }
                rows = db.execute(
                    """SELECT event_id, event_type, occurred_at, source_kind,
                              source_identifier, rationale, subject_id, object_id
                       FROM world_events WHERE object_id IS NOT NULL ORDER BY sequence""").fetchall()
                for event in rows:
                    relation_type = relation_by_event.get(event["event_type"])
                    if relation_type is None:
                        continue
                    source = db.execute("SELECT entity_type FROM atlas_entities WHERE entity_id = ?",
                                        (event["subject_id"],)).fetchone()
                    target = db.execute("SELECT entity_type FROM atlas_entities WHERE entity_id = ?",
                                        (event["object_id"],)).fetchone()
                    if source is None or target is None:
                        raise ValueError("Existing world event references an entity outside the Atlas graph.")
                    self.contracts.validate_relationship(relation_type, source["entity_type"], target["entity_type"])
                    db.execute(
                        """INSERT OR IGNORE INTO knowledge_relationships(
                               relationship_id, relation_type, source_entity_id,
                               target_entity_id, recorded_at, source_event_id,
                               source_kind, source_identifier, rationale
                           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (str(uuid.uuid5(uuid.NAMESPACE_URL, f"atlas:event:{event['event_id']}")),
                         relation_type, event["subject_id"], event["object_id"], event["occurred_at"],
                         event["event_id"], event["source_kind"], event["source_identifier"], event["rationale"]),
                    )
                db.execute("COMMIT")
            except Exception:
                db.execute("ROLLBACK")
                raise

    def _last_tick_from_db(self, player_id: str) -> int:
        with closing(self.connect()) as db:
            row = db.execute("SELECT last_tick FROM player_states WHERE player_id = ?", (player_id,)).fetchone()
        if row is None:
            raise ValueError("Player profile is unavailable.")
        return int(row["last_tick"])

    def create_session(self) -> dict[str, str]:
        """Assign the first free local traveler seat to a new browser tab."""
        with self._command_lock:
            self._expire_sessions(time.monotonic())
            player_id = next((pid for pid in PLAYER_ENTITY_IDS if pid not in self._seat_by_player), None)
            if player_id is None:
                raise SessionCapacityError("Both local traveler seats are active. Closed or idle sessions are released automatically.")
            token = secrets.token_urlsafe(32)
            self._sessions[token] = player_id
            self._seat_by_player[player_id] = token
            self._session_last_seen[token] = time.monotonic()
            return {"session_token": token, "player_id": player_id, "player_name": PLAYER_NAMES[player_id]}

    def close_session(self, token: str | None) -> bool:
        """Release a browser seat and persist a stopped traveler state."""
        if not isinstance(token, str):
            return False
        with self._command_lock:
            player_id = self._sessions.get(token)
            if player_id is None:
                return False
            self._release_session(token, player_id)
            return True

    def player_for_session(self, token: str | None) -> str | None:
        if not isinstance(token, str):
            return None
        with self._command_lock:
            now = time.monotonic()
            self._expire_sessions(now)
            player_id = self._sessions.get(token)
            if player_id is not None:
                self._session_last_seen[token] = now
            return player_id

    def _expire_sessions(self, now: float) -> None:
        expired = [key for key, seen in self._session_last_seen.items()
                   if now - seen > SESSION_IDLE_TTL_SECONDS]
        for key in expired:
            player_id = self._sessions.get(key)
            if player_id is not None:
                self._release_session(key, player_id)

    def _release_session(self, token: str, player_id: str) -> None:
        occurred_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        event_id = str(uuid.uuid4())
        source_identifier = str(uuid.uuid4())
        rationale = f"{PLAYER_NAMES[player_id]}'s local session was released; movement stopped."
        payload = {"vx": 0.0, "vz": 0.0}
        with closing(self.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                player_row = db.execute(
                    "SELECT state_json FROM player_states WHERE player_id = ?", (player_id,)
                ).fetchone()
                world_row = db.execute(
                    "SELECT version FROM world_state WHERE singleton = 1"
                ).fetchone()
                if player_row is None or world_row is None:
                    raise ValueError("Cannot release a session without its player projection.")
                event_contract = {
                    "event_id": event_id,
                    "event_type": "PlayerSessionReleased",
                    "schema_version": 1,
                    "occurred_at": occurred_at,
                    "actor_id": player_id,
                    "source_kind": "session_lifecycle",
                    "source_identifier": source_identifier,
                    "rationale": rationale,
                    "subject_id": player_id,
                    "object_id": None,
                }
                self.contracts.validate_event(event_contract)
                state = json.loads(player_row["state_json"])
                state["player"].update(payload)
                db.execute(
                    """INSERT INTO world_events(
                           event_id, schema_version, occurred_at, event_type, actor_id,
                           source_kind, source_identifier, rationale, subject_id, object_id, payload_json
                       ) VALUES (?, 1, ?, 'PlayerSessionReleased', ?, 'session_lifecycle', ?, ?, ?, NULL, ?)""",
                    (event_id, occurred_at, player_id, source_identifier, rationale, player_id,
                     json.dumps(payload, separators=(",", ":"), sort_keys=True)),
                )
                db.execute("UPDATE player_states SET state_json = ? WHERE player_id = ?",
                           (json.dumps(state, separators=(",", ":")), player_id))
                db.execute(
                    "UPDATE world_state SET version = ? WHERE singleton = 1",
                    (world_row["version"] + 1,),
                )
                db.execute("COMMIT")
            except Exception:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise
        self._sessions.pop(token, None)
        self._session_last_seen.pop(token, None)
        if self._seat_by_player.get(player_id) == token:
            del self._seat_by_player[player_id]
        runtime = self._runtime[player_id]
        runtime["active_input"] = {"x": 0.0, "z": 0.0}
        runtime["active_run"] = False
        runtime["sim_accumulator"] = 0.0

    def session_count(self) -> int:
        with self._command_lock:
            self._expire_sessions(time.monotonic())
            return len(self._sessions)

    def read(self, player_id: str = PLAYER_ENTITY_ID) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        if player_id not in PLAYER_ENTITY_IDS:
            raise ValueError("Player profile is unavailable.")
        with closing(self.connect()) as db:
            shared_row = db.execute("SELECT state_json FROM world_state WHERE singleton = 1").fetchone()
            player_rows = db.execute("SELECT player_id, player_name, state_json, last_tick FROM player_states ORDER BY player_id").fetchall()
            profile_rows = db.execute("SELECT player_id, appearance_json FROM player_profiles").fetchall()
            events = db.execute(
                "SELECT sequence, event_id, schema_version, event_type, occurred_at, actor_id, source_kind, source_identifier, rationale, subject_id, object_id, payload_json FROM world_events ORDER BY sequence DESC LIMIT 8"
            ).fetchall()
        shared = json.loads(shared_row["state_json"])
        players_by_id = {row["player_id"]: (row, json.loads(row["state_json"])) for row in player_rows}
        appearances_by_id = {
            row["player_id"]: json.loads(row["appearance_json"]) for row in profile_rows
        }
        row, personal = players_by_id[player_id]
        state = {**shared, **personal, "appearance": appearances_by_id[player_id]}
        state["players"] = [
            {"id": pid, "name": player_row["player_name"], "x": saved["player"]["x"],
             "y": saved["player"]["y"], "vx": saved["player"].get("vx", 0.0),
             "vz": saved["player"].get("vz", 0.0), "last_processed_input": player_row["last_tick"],
             "height": saved["player"].get("height", 0.0),
             "vertical_velocity": saved["player"].get("vy", 0.0),
             "grounded": saved["player"].get("grounded", True),
             "is_self": pid == player_id}
            for pid, (player_row, saved) in players_by_id.items()
        ]
        recent = [{"sequence": e["sequence"], "event_id": e["event_id"], "schema_version": e["schema_version"],
                   "type": e["event_type"], "at": e["occurred_at"], "actor_id": e["actor_id"],
                   "source": {"kind": e["source_kind"], "identifier": e["source_identifier"]},
                   "rationale": e["rationale"], "subject_id": e["subject_id"], "object_id": e["object_id"],
                   "detail": json.loads(e["payload_json"])} for e in reversed(events)]
        return state, recent

    def save_appearance(self, player_id: str, appearance: Any) -> dict[str, Any]:
        if player_id not in PLAYER_ENTITY_IDS:
            raise ValueError("Player profile is unavailable.")
        profile = validate_appearance(appearance)
        with self._command_lock, closing(self.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute("SELECT 1 FROM player_profiles WHERE player_id = ?", (player_id,)).fetchone()
                if row is None:
                    raise ValueError("Player profile is unavailable.")
                db.execute(
                    "UPDATE player_profiles SET appearance_json = ? WHERE player_id = ?",
                    (json.dumps(profile, separators=(",", ":")), player_id),
                )
                db.execute("COMMIT")
            except Exception:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise
        return profile

    @staticmethod
    def _canonical_uuid(value: str | None, label: str) -> str | None:
        if value is None:
            return None
        try:
            canonical = str(uuid.UUID(value))
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError(f"{label} must be a UUID.") from exc
        if canonical != value:
            raise ValueError(f"{label} must use canonical UUID formatting.")
        return canonical

    def query_knowledge(self, *, source_id: str | None = None, target_id: str | None = None,
                        entity_id: str | None = None, relation_type: str | None = None,
                        limit: int = 100) -> dict[str, Any]:
        """Return durable graph edges with their authored provenance for explanation."""
        source_id = self._canonical_uuid(source_id, "source")
        target_id = self._canonical_uuid(target_id, "target")
        entity_id = self._canonical_uuid(entity_id, "entity")
        if relation_type is not None and relation_type not in self.contracts.relationships:
            raise ValueError("Relationship type is not declared in the Atlas ontology.")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200:
            raise ValueError("Knowledge query limit must be between 1 and 200.")

        conditions: list[str] = []
        params: list[Any] = []
        if source_id is not None:
            conditions.append("kr.source_entity_id = ?")
            params.append(source_id)
        if target_id is not None:
            conditions.append("kr.target_entity_id = ?")
            params.append(target_id)
        if entity_id is not None:
            conditions.append("(kr.source_entity_id = ? OR kr.target_entity_id = ?)")
            params.extend((entity_id, entity_id))
        if relation_type is not None:
            conditions.append("kr.relation_type = ?")
            params.append(relation_type)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with closing(self.connect()) as db:
            rows = db.execute(
                f"""SELECT kr.relationship_id, kr.relation_type, kr.source_entity_id,
                           kr.target_entity_id, kr.recorded_at, kr.source_event_id,
                           kr.source_kind, kr.source_identifier, kr.rationale,
                           e.actor_id
                    FROM knowledge_relationships kr
                    LEFT JOIN world_events e ON e.event_id = kr.source_event_id
                    {where}
                    ORDER BY kr.recorded_at, kr.relationship_id LIMIT ?""",
                (*params, limit),
            ).fetchall()
            entity_ids = {row["source_entity_id"] for row in rows} | {row["target_entity_id"] for row in rows}
            if not conditions:
                entity_rows = db.execute(
                    "SELECT entity_id, entity_type, created_at, attributes_json FROM atlas_entities ORDER BY entity_id"
                ).fetchall()
            else:
                entity_ids.update(value for value in (source_id, target_id, entity_id) if value)
                entity_rows = []
                if entity_ids:
                    placeholders = ",".join("?" for _ in entity_ids)
                    entity_rows = db.execute(
                        f"SELECT entity_id, entity_type, created_at, attributes_json FROM atlas_entities WHERE entity_id IN ({placeholders}) ORDER BY entity_id",
                        tuple(sorted(entity_ids)),
                    ).fetchall()
        entities = [{"id": row["entity_id"], "type": row["entity_type"],
                     "created_at": row["created_at"], "attributes": json.loads(row["attributes_json"])}
                    for row in entity_rows]
        relationships = [{
            "id": row["relationship_id"], "type": row["relation_type"],
            "source_id": row["source_entity_id"], "target_id": row["target_entity_id"],
            "recorded_at": row["recorded_at"], "event_id": row["source_event_id"],
            "actor_id": row["actor_id"],
            "source": {"kind": row["source_kind"], "identifier": row["source_identifier"]},
            "rationale": row["rationale"],
        } for row in rows]
        return {"entities": entities, "relationships": relationships, "limit": limit}

    def query_memory(self, *, entity_id: str | None = None, event_type: str | None = None,
                     after_sequence: int = 0, limit: int = 50) -> list[dict[str, Any]]:
        """Read the append-only world history in event-time order with rationale."""
        entity_id = self._canonical_uuid(entity_id, "entity")
        if event_type is not None and event_type not in {
            "PlayerMoved", "ResourceGathered", "NPCSpokenTo", "BeaconAwakened",
            "CreatureDamaged", "PlayerGuarded", "PlayerDodged", "CreatureReawakened",
            "EntityCreated", "RelationshipEstablished",
        }:
            raise ValueError("Event type is not registered by the reference runtime.")
        if isinstance(after_sequence, bool) or not isinstance(after_sequence, int) or after_sequence < 0:
            raise ValueError("Memory cursor must be a non-negative event sequence.")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200:
            raise ValueError("Memory query limit must be between 1 and 200.")
        clauses, params = ["sequence > ?"], [after_sequence]
        if entity_id is not None:
            clauses.append("(actor_id = ? OR subject_id = ? OR object_id = ?)")
            params.extend((entity_id, entity_id, entity_id))
        if event_type is not None:
            clauses.append("event_type = ?")
            params.append(event_type)
        with closing(self.connect()) as db:
            rows = db.execute(
                f"""SELECT sequence, event_id, schema_version, event_type, occurred_at,
                           actor_id, source_kind, source_identifier, rationale,
                           subject_id, object_id, payload_json
                    FROM world_events WHERE {' AND '.join(clauses)}
                    ORDER BY sequence LIMIT ?""",
                (*params, limit),
            ).fetchall()
        return [{"sequence": row["sequence"], "event_id": row["event_id"],
                 "schema_version": row["schema_version"], "type": row["event_type"],
                 "at": row["occurred_at"], "actor_id": row["actor_id"],
                 "source": {"kind": row["source_kind"], "identifier": row["source_identifier"]},
                 "rationale": row["rationale"], "subject_id": row["subject_id"],
                 "object_id": row["object_id"], "detail": json.loads(row["payload_json"])}
                for row in rows]

    def query_analytics(self, *, after_sequence: int = 0, limit: int = 1000) -> dict[str, Any]:
        """Return a cursor-paged, deterministic analytics window over world history."""
        if isinstance(after_sequence, bool) or not isinstance(after_sequence, int) or after_sequence < 0:
            raise ValueError("Analytics cursor must be a non-negative event sequence.")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 5000:
            raise ValueError("Analytics page size must be between 1 and 5000.")
        with closing(self.connect()) as db:
            rows = db.execute(
                """SELECT sequence, event_id, schema_version, event_type, occurred_at,
                          actor_id, source_kind, source_identifier, rationale,
                          subject_id, object_id, payload_json
                   FROM world_events WHERE sequence > ? ORDER BY sequence LIMIT ?""",
                (after_sequence, limit + 1),
            ).fetchall()
        has_more = len(rows) > limit
        page = rows[:limit]
        events = [{"sequence": row["sequence"], "event_id": row["event_id"],
                   "schema_version": row["schema_version"], "type": row["event_type"],
                   "at": row["occurred_at"], "actor_id": row["actor_id"],
                   "source": {"kind": row["source_kind"], "identifier": row["source_identifier"]},
                   "rationale": row["rationale"], "subject_id": row["subject_id"],
                   "object_id": row["object_id"], "detail": json.loads(row["payload_json"])}
                  for row in page]
        return summarize_events(events, after_sequence=after_sequence, has_more=has_more)

    def run_simulation(self, proposal: dict[str, Any], actor_id: str) -> dict[str, Any]:
        """Persist a reproducible analysis without writing to world state/history."""
        if actor_id not in PLAYER_ENTITY_IDS:
            raise ValueError("A local traveler session is required to run simulations.")
        with closing(self.connect()) as db:
            db.execute("BEGIN")
            try:
                rows = db.execute(
                    """SELECT sequence, event_id, event_type, actor_id, payload_json
                       FROM world_events ORDER BY sequence LIMIT ?""",
                    (MAX_SIMULATION_EVENT_HISTORY + 1,),
                ).fetchall()
                if len(rows) > MAX_SIMULATION_EVENT_HISTORY:
                    raise ValueError(
                        "Simulation event history exceeds the "
                        f"{MAX_SIMULATION_EVENT_HISTORY}-event limit."
                    )
                db.execute("COMMIT")
            except Exception:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise
        events = [{"sequence": row["sequence"], "event_id": row["event_id"],
                   "type": row["event_type"], "actor_id": row["actor_id"],
                   "detail": json.loads(row["payload_json"])} for row in rows]
        result = simulate_recorded_events(events, proposal)
        simulation_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        as_of_sequence = int(rows[-1]["sequence"]) if rows else 0
        result = {"simulation_id": simulation_id, "created_at": created_at,
                  "as_of_sequence": as_of_sequence,
                  "baseline_state": {"kind": "event_log_snapshot",
                                     "through_event_sequence": as_of_sequence},
                  "created_by": actor_id, **result}
        with self._command_lock, closing(self.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                db.execute(
                    """INSERT INTO simulation_runs(
                           simulation_id, model, model_version, created_at, as_of_sequence,
                           actor_id, proposal_json, result_json
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (simulation_id, result["model"], result["model_version"], created_at,
                     as_of_sequence, actor_id,
                     json.dumps(proposal, separators=(",", ":"), sort_keys=True),
                     json.dumps(result, separators=(",", ":"), sort_keys=True)),
                )
                db.execute("COMMIT")
            except Exception:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise
        return result

    def get_simulation(self, simulation_id: str) -> dict[str, Any] | None:
        simulation_id = self._canonical_uuid(simulation_id, "simulation")
        with closing(self.connect()) as db:
            row = db.execute("SELECT result_json FROM simulation_runs WHERE simulation_id = ?",
                             (simulation_id,)).fetchone()
        return json.loads(row["result_json"]) if row else None

    def evaluate_policy(self, simulation_id: str, actor_id: str) -> dict[str, Any]:
        """Record a fail-closed policy evaluation; never apply the proposal."""
        simulation_id = self._canonical_uuid(simulation_id, "simulation")
        if actor_id not in PLAYER_ENTITY_IDS:
            raise ValueError("A local traveler session is required to evaluate policy.")
        with self._command_lock, closing(self.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT result_json FROM simulation_runs WHERE simulation_id = ?",
                             (simulation_id,)).fetchone()
            if row is None:
                db.execute("ROLLBACK")
                raise ValueError("A persisted simulation is required for policy evaluation.")
            simulation = json.loads(row["result_json"])
            result = self.policy_engine.evaluate(simulation)
            evaluation_id = str(uuid.uuid4())
            created_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
            result = {"evaluation_id": evaluation_id, "created_at": created_at,
                      "created_by": actor_id, **result}
            db.execute(
                """INSERT INTO policy_evaluations(
                       evaluation_id, simulation_id, actor_id, created_at, result_json
                   ) VALUES (?, ?, ?, ?, ?)""",
                (evaluation_id, simulation_id, actor_id, created_at,
                 json.dumps(result, separators=(",", ":"), sort_keys=True)),
            )
            db.execute("COMMIT")
            return result

    def get_policy_evaluation(self, evaluation_id: str) -> dict[str, Any] | None:
        evaluation_id = self._canonical_uuid(evaluation_id, "policy evaluation")
        with closing(self.connect()) as db:
            row = db.execute("SELECT result_json FROM policy_evaluations WHERE evaluation_id = ?",
                             (evaluation_id,)).fetchone()
        return json.loads(row["result_json"]) if row else None

    def create_decision(self, simulation_id: str, evaluation_id: str, actor_id: str) -> dict[str, Any]:
        simulation_id = self._canonical_uuid(simulation_id, "simulation")
        evaluation_id = self._canonical_uuid(evaluation_id, "policy evaluation")
        if actor_id not in PLAYER_ENTITY_IDS:
            raise ValueError("A local traveler session is required to create a decision.")
        with self._command_lock, closing(self.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            simulation_row = db.execute("SELECT result_json FROM simulation_runs WHERE simulation_id = ?",
                                        (simulation_id,)).fetchone()
            evaluation_row = db.execute(
                "SELECT result_json FROM policy_evaluations WHERE evaluation_id = ? AND simulation_id = ?",
                (evaluation_id, simulation_id)).fetchone()
            if simulation_row is None or evaluation_row is None:
                db.execute("ROLLBACK")
                raise ValueError("A persisted simulation and its matching policy evaluation are required.")
            simulation = json.loads(simulation_row["result_json"])
            policy_result = json.loads(evaluation_row["result_json"])
            result = generate_decision(simulation, policy_result)
            decision_id = str(uuid.uuid4())
            created_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
            result = {"decision_id": decision_id, "created_at": created_at,
                      "created_by": actor_id, **result}
            db.execute(
                """INSERT INTO atlas_decisions(
                       decision_id, simulation_id, evaluation_id, actor_id, created_at, result_json
                   ) VALUES (?, ?, ?, ?, ?, ?)""",
                (decision_id, simulation_id, evaluation_id, actor_id, created_at,
                 json.dumps(result, separators=(",", ":"), sort_keys=True)),
            )
            db.execute("COMMIT")
            return result

    def get_decision(self, decision_id: str) -> dict[str, Any] | None:
        decision_id = self._canonical_uuid(decision_id, "decision")
        with closing(self.connect()) as db:
            row = db.execute("SELECT result_json FROM atlas_decisions WHERE decision_id = ?",
                             (decision_id,)).fetchone()
            review = db.execute("SELECT result_json FROM decision_reviews WHERE decision_id = ?",
                                (decision_id,)).fetchone()
        if row is None:
            return None
        result = json.loads(row["result_json"])
        if review is not None:
            result["human_review"] = json.loads(review["result_json"])
            result["status"] = result["human_review"]["status"]
        return result

    def review_decision(self, decision_id: str, action: str, rationale: str,
                        reviewer_id: str) -> dict[str, Any]:
        """Append one human review to a pending decision; deployment remains separate."""
        decision_id = self._canonical_uuid(decision_id, "decision")
        if reviewer_id not in PLAYER_ENTITY_IDS:
            raise ValueError("A local human reviewer session is required.")
        if not isinstance(action, str) or action not in {"approve", "reject", "delay", "escalate"}:
            raise ValueError("Review action must be approve, reject, delay, or escalate.")
        if not isinstance(rationale, str) or not 12 <= len(rationale.strip()) <= 1000:
            raise ValueError("A review rationale must contain 12 to 1000 characters.")
        with self._command_lock, closing(self.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            decision_row = db.execute("SELECT result_json FROM atlas_decisions WHERE decision_id = ?",
                                      (decision_id,)).fetchone()
            if decision_row is None:
                db.execute("ROLLBACK")
                raise ValueError("Decision was not found.")
            decision = json.loads(decision_row["result_json"])
            existing = db.execute("SELECT 1 FROM decision_reviews WHERE decision_id = ?",
                                  (decision_id,)).fetchone()
            if existing:
                db.execute("ROLLBACK")
                raise ValueError("This decision already has a human review.")
            if decision.get("status") != "awaiting_human_approval":
                db.execute("ROLLBACK")
                raise ValueError("Only policy-eligible decisions awaiting human approval can be reviewed.")
            if action == "approve" and (decision.get("recommended_output") != "approve" or
                                         decision.get("policy_status") != "eligible_for_human_review"):
                db.execute("ROLLBACK")
                raise ValueError("A policy-blocked recommendation cannot be approved.")
            status = {"approve": "approved_pending_deployment", "reject": "rejected_by_human",
                      "delay": "delayed_by_human", "escalate": "escalated_by_human"}[action]
            review_id = str(uuid.uuid4())
            reviewed_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
            result = {"review_id": review_id, "decision_id": decision_id,
                      "reviewer_id": reviewer_id, "action": action, "rationale": rationale.strip(),
                      "status": status, "reviewed_at": reviewed_at,
                      "world_change_applied": False}
            db.execute(
                """INSERT INTO decision_reviews(
                       review_id, decision_id, reviewer_id, action, rationale, reviewed_at, result_json
                   ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (review_id, decision_id, reviewer_id, action, rationale.strip(), reviewed_at,
                 json.dumps(result, separators=(",", ":"), sort_keys=True)),
            )
            db.execute("COMMIT")
            return result

    def explain_event(self, event_id: str) -> dict[str, Any] | None:
        """Load an immutable event with its entity and graph context."""
        event_id = self._canonical_uuid(event_id, "event")
        with closing(self.connect()) as db:
            row = db.execute(
                """SELECT sequence, event_id, schema_version, event_type, occurred_at,
                          actor_id, source_kind, source_identifier, rationale,
                          subject_id, object_id, payload_json
                   FROM world_events WHERE event_id = ?""",
                (event_id,),
            ).fetchone()
            if row is None:
                return None
            event = {"sequence": row["sequence"], "event_id": row["event_id"],
                     "schema_version": row["schema_version"], "type": row["event_type"],
                     "at": row["occurred_at"], "actor_id": row["actor_id"],
                     "source": {"kind": row["source_kind"], "identifier": row["source_identifier"]},
                     "rationale": row["rationale"], "subject_id": row["subject_id"],
                     "object_id": row["object_id"], "detail": json.loads(row["payload_json"])}
            ids = {value for value in (row["actor_id"], row["subject_id"], row["object_id"]) if value}
            placeholders = ",".join("?" for _ in ids)
            entity_rows = db.execute(
                f"""SELECT entity_id, entity_type, created_at, attributes_json
                     FROM atlas_entities WHERE entity_id IN ({placeholders}) ORDER BY entity_id""",
                tuple(sorted(ids)),
            ).fetchall()
            relationships = db.execute(
                """SELECT relationship_id, relation_type, source_entity_id, target_entity_id,
                          recorded_at, source_event_id, source_kind, source_identifier, rationale
                   FROM knowledge_relationships WHERE source_event_id = ? ORDER BY relationship_id""",
                (event_id,),
            ).fetchall()
        entities = [{"id": item["entity_id"], "type": item["entity_type"],
                     "created_at": item["created_at"], "attributes": json.loads(item["attributes_json"])}
                    for item in entity_rows]
        relation_records = [{"id": item["relationship_id"], "type": item["relation_type"],
                             "source_id": item["source_entity_id"], "target_id": item["target_entity_id"],
                             "recorded_at": item["recorded_at"], "event_id": item["source_event_id"],
                             "source": {"kind": item["source_kind"], "identifier": item["source_identifier"]},
                             "rationale": item["rationale"]} for item in relationships]
        return {"event": event, "entities": entities, "relationships": relation_records}

    @staticmethod
    def _authored_event(event_type: str, subject_id: str, object_id: str | None,
                        source_kind: str, source_identifier: str, rationale: str,
                        detail: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
        event_id = str(uuid.uuid4())
        occurred_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        contract = {"event_id": event_id, "event_type": event_type, "schema_version": 1,
                    "occurred_at": occurred_at, "actor_id": CREATOR_ENTITY_ID,
                    "source_kind": source_kind, "source_identifier": source_identifier,
                    "rationale": rationale, "subject_id": subject_id, "object_id": object_id}
        payload = {"detail": detail}
        return event_id, occurred_at, {**contract, "payload": payload}

    def create_entity(self, entity: dict[str, Any], *, source_kind: str,
                      source_identifier: str, rationale: str) -> dict[str, Any]:
        """Persist a creator-authored entity and its provenance event atomically."""
        self.contracts.validate_entity(entity)
        if not isinstance(rationale, str) or not rationale.strip():
            raise ValueError("Entity creation requires an authored rationale.")
        if not isinstance(source_kind, str) or not source_kind.strip():
            raise ValueError("Entity creation requires a source kind.")
        with self._command_lock, closing(self.connect()) as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                existing = db.execute("SELECT 1 FROM atlas_entities WHERE entity_id = ?", (entity["id"],)).fetchone()
                if existing:
                    raise ValueError("Entity ID already exists in the Atlas world model.")
                known_types = {row["entity_id"]: row["entity_type"] for row in db.execute(
                    "SELECT entity_id, entity_type FROM atlas_entities").fetchall()}
                known_types[entity["id"]] = entity["type"]
                event_id, occurred_at, contract = self._authored_event(
                    "EntityCreated", CREATOR_ENTITY_ID, entity["id"], source_kind,
                    source_identifier, rationale.strip(), {"entity": entity})
                self.contracts.validate_event(contract, entity_types=known_types)
                db.execute(
                    """INSERT INTO world_events(
                           event_id, schema_version, occurred_at, event_type, actor_id,
                           source_kind, source_identifier, rationale, subject_id, object_id, payload_json
                       ) VALUES (?, 1, ?, 'EntityCreated', ?, ?, ?, ?, ?, ?, ?)""",
                    (event_id, occurred_at, CREATOR_ENTITY_ID, source_kind, source_identifier,
                     rationale.strip(), CREATOR_ENTITY_ID, entity["id"],
                     json.dumps({"entity": entity}, separators=(",", ":"), sort_keys=True)),
                )
                attributes = {key: value for key, value in entity.items()
                              if key not in {"id", "type", "created_at"}}
                db.execute(
                    "INSERT INTO atlas_entities(entity_id, entity_type, created_at, attributes_json) VALUES (?, ?, ?, ?)",
                    (entity["id"], entity["type"], entity["created_at"],
                     json.dumps(attributes, separators=(",", ":"), sort_keys=True)),
                )
                db.execute("UPDATE world_state SET version = version + 1 WHERE singleton = 1")
                db.execute("COMMIT")
            except Exception:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise
        return {"event_id": event_id, "event_type": "EntityCreated", "at": occurred_at,
                "actor_id": CREATOR_ENTITY_ID, "source": {"kind": source_kind, "identifier": source_identifier},
                "rationale": rationale.strip(), "subject_id": CREATOR_ENTITY_ID,
                "object_id": entity["id"], "detail": {"entity": entity}}

    def create_relationship(self, relation_type: str, source_id: str, target_id: str, *,
                            source_kind: str, source_identifier: str, rationale: str) -> dict[str, Any]:
        """Record an ontology-checked relationship and explanation event atomically."""
        if not isinstance(rationale, str) or not rationale.strip():
            raise ValueError("Relationship creation requires an authored rationale.")
        if not isinstance(source_kind, str) or not source_kind.strip():
            raise ValueError("Relationship creation requires a source kind.")
        if not isinstance(relation_type, str):
            raise ValueError("Relationship type must be a declared string.")
        source_id = self._canonical_uuid(source_id, "relationship source")
        target_id = self._canonical_uuid(target_id, "relationship target")
        with self._command_lock, closing(self.connect()) as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                rows = db.execute("SELECT entity_id, entity_type FROM atlas_entities").fetchall()
                known_types = {row["entity_id"]: row["entity_type"] for row in rows}
                source_type, target_type = known_types.get(source_id), known_types.get(target_id)
                if source_type is None or target_type is None:
                    raise ValueError("Relationship endpoints must already exist in the Atlas world model.")
                self.contracts.validate_relationship(relation_type, source_type, target_type)
                duplicate = db.execute(
                    """SELECT 1 FROM knowledge_relationships
                       WHERE relation_type = ? AND source_entity_id = ? AND target_entity_id = ?""",
                    (relation_type, source_id, target_id),
                ).fetchone()
                if duplicate:
                    raise ValueError("That relationship already exists in the Atlas world model.")
                event_id, occurred_at, contract = self._authored_event(
                    "RelationshipEstablished", source_id, target_id, source_kind,
                    source_identifier, rationale.strip(), {"relationship_type": relation_type})
                self.contracts.validate_event(contract, relation_type, known_types)
                db.execute(
                    """INSERT INTO world_events(
                           event_id, schema_version, occurred_at, event_type, actor_id,
                           source_kind, source_identifier, rationale, subject_id, object_id, payload_json
                       ) VALUES (?, 1, ?, 'RelationshipEstablished', ?, ?, ?, ?, ?, ?, ?)""",
                    (event_id, occurred_at, CREATOR_ENTITY_ID, source_kind, source_identifier,
                     rationale.strip(), source_id, target_id,
                     json.dumps({"relationship_type": relation_type}, separators=(",", ":"))),
                )
                db.execute(
                    """INSERT INTO knowledge_relationships(
                           relationship_id, relation_type, source_entity_id,
                           target_entity_id, recorded_at, source_event_id,
                           source_kind, source_identifier, rationale
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (str(uuid.uuid5(uuid.NAMESPACE_URL, f"atlas:event:{event_id}")), relation_type,
                     source_id, target_id, occurred_at, event_id, source_kind, source_identifier,
                     rationale.strip()),
                )
                db.execute("UPDATE world_state SET version = version + 1 WHERE singleton = 1")
                db.execute("COMMIT")
            except Exception:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise
        return {"event_id": event_id, "event_type": "RelationshipEstablished", "at": occurred_at,
                "actor_id": CREATOR_ENTITY_ID, "source": {"kind": source_kind, "identifier": source_identifier},
                "rationale": rationale.strip(), "subject_id": source_id, "object_id": target_id,
                "detail": {"relationship_type": relation_type}}

    @property
    def last_input_sequence(self) -> int:
        return self.last_input_sequence_for(PLAYER_ENTITY_ID)

    def last_input_sequence_for(self, player_id: str) -> int:
        return self._last_tick_from_db(player_id)

    @property
    def _last_input_sequence(self) -> int:
        return self._runtime[PLAYER_ENTITY_ID]["last_tick"]

    @_last_input_sequence.setter
    def _last_input_sequence(self, value: int) -> None:
        self._runtime[PLAYER_ENTITY_ID]["last_tick"] = value
        with closing(self.connect()) as db:
            db.execute("UPDATE player_states SET last_tick = ? WHERE player_id = ?", (value, PLAYER_ENTITY_ID))

    @property
    def _player_history(self) -> EntityHistory:
        return self._runtime[PLAYER_ENTITY_ID]["history"]

    @_player_history.setter
    def _player_history(self, value: EntityHistory) -> None:
        if hasattr(self, "_runtime") and PLAYER_ENTITY_ID in self._runtime:
            self._runtime[PLAYER_ENTITY_ID]["history"] = value

    def command(self, action: dict[str, Any], player_id: str = PLAYER_ENTITY_ID) -> dict[str, Any]:
        if player_id not in PLAYER_ENTITY_IDS:
            raise ValueError("Player profile is unavailable.")
        action = validate_action(action)
        with self._command_lock:
            return self._command_locked(action, player_id)

    def _command_locked(self, action: dict[str, Any], player_id: str) -> dict[str, Any]:
        runtime = self._runtime[player_id]
        db = self.connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT version, state_json FROM world_state WHERE singleton = 1").fetchone()
            profile = db.execute("SELECT state_json, last_tick FROM player_states WHERE player_id = ?", (player_id,)).fetchone()
            shared = json.loads(row["state_json"])
            personal = json.loads(profile["state_json"])
            state = {**shared, **personal}
            input_sequence = None
            movement_frames = None
            other_players = db.execute("SELECT player_id, state_json FROM player_states WHERE player_id != ?", (player_id,)).fetchall()
            dynamic_obstacles = [
                {"x": saved["player"]["x"], "z": saved["player"]["y"], "radius": .2}
                for saved in (json.loads(item["state_json"]) for item in other_players)
            ]
            from .world import WORLD_OBSTACLES
            collision_obstacles = [*WORLD_OBSTACLES, *dynamic_obstacles]
            if action.get("type") == "move":
                input_sequence = action.get("sequence")
                if isinstance(input_sequence, bool) or not isinstance(input_sequence, int) or input_sequence < 1:
                    raise ValueError("Movement input sequence is invalid.")
                cached = runtime["ack_cache"].get(input_sequence)
                if cached is not None:
                    db.execute("ROLLBACK")
                    return cached
                last_tick = int(profile["last_tick"])
                if input_sequence <= last_tick:
                    raise ValueError("Movement input sequence is stale.")
                movement_frames = action.get("frames")
                if movement_frames is not None:
                    if not isinstance(movement_frames, list) or not 1 <= len(movement_frames) <= 32:
                        raise ValueError("Movement frame batch must contain between 1 and 32 frames.")
                    expected_tick = last_tick + 1
                    normalized_frames = []
                    for frame in movement_frames:
                        if not isinstance(frame, dict) or frame.get("sequence") != expected_tick:
                            raise ValueError("Movement frame sequence is invalid or contains a gap.")
                        frame_input = normalize_movement(frame.get("input"), frame.get("run"))
                        jump = frame.get("jump", False)
                        if not isinstance(jump, bool):
                            raise ValueError("Jump input must be boolean.")
                        normalized_frames.append({"sequence": expected_tick, "input": frame_input,
                                                  "run": frame["run"], "jump": jump})
                        expected_tick += 1
                    if normalized_frames[-1]["sequence"] != input_sequence:
                        raise ValueError("Movement acknowledgement must match the final frame.")
                    movement_frames = normalized_frames
                    final_frame = movement_frames[-1]
                    requested_input, requested_run = final_frame["input"], final_frame["run"]
                    requested_jump = final_frame["jump"]
                    action = {**action, "input": requested_input, "run": requested_run, "jump": requested_jump}
                else:
                    now = time.monotonic()
                    requested_input = normalize_movement(action.get("input"), action.get("run", False))
                    requested_run = action.get("run", False)
                    requested_jump = action.get("jump", False)
                    if not isinstance(requested_jump, bool):
                        raise ValueError("Jump input must be boolean.")
                    elapsed = min(max(now - runtime["last_sim_tick"], 0.0), 0.33)
                    runtime["last_sim_tick"] = now
                    accumulated = runtime["sim_accumulator"] + elapsed
                    fixed_step = 1.0 / 60.0
                    steps = int((accumulated + 1e-12) / fixed_step)
                    sim_dt = steps * fixed_step
                    runtime["sim_accumulator"] = accumulated - sim_dt
                    action = {**action, "input": requested_input, "_sim_input": runtime["active_input"],
                              "_sim_run": runtime["active_run"], "dt": sim_dt, "_obstacles": collision_obstacles}
                state["player"].setdefault("vx", 0.0)
                state["player"].setdefault("vz", 0.0)
            trusted_context = None
            if action.get("type") == "attack" and "rewind_sequence" in action:
                rewind_sequence = action["rewind_sequence"]
                if isinstance(rewind_sequence, bool) or not isinstance(rewind_sequence, int):
                    raise ValueError("Attack rewind sequence is invalid.")
                if rewind_sequence <= int(profile["last_tick"]):
                    now = time.monotonic()
                    attacker_history = runtime["history"].rewind_sequence(rewind_sequence, now)
                    target_history = self._target_history.rewind(attacker_history.time) if attacker_history else None
                    if attacker_history is not None and target_history is not None:
                        trusted_context = {
                            "attack_origin": {"x": attacker_history.x, "y": attacker_history.z},
                            "rewound_target": {"x": target_history.x, "y": target_history.z,
                                               "radius": target_history.radius, "height": target_history.height},
                            "rewind_applied": True,
                        }
            if movement_frames is not None:
                state, event_type, payload = state, "PlayerMoved", {}
                for frame in movement_frames:
                    frame_action = {"type": "move", "input": frame["input"], "run": frame["run"],
                                    "jump": frame["jump"],
                                    "_sim_input": frame["input"], "_sim_run": frame["run"], "dt": 1.0 / 60.0,
                                    "_obstacles": collision_obstacles}
                    state, event_type, payload = apply_action(state, frame_action)
            else:
                state, event_type, payload = apply_action(
                    state, action, trusted_context=trusted_context)

            now = time.monotonic()
            occurred_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
            event_id, source_identifier = str(uuid.uuid4()), str(uuid.uuid4())
            object_id = WORLD_ENTITY_IDS.get(action.get("target"))
            relation_for_event = {
                "ResourceGathered": "gathers", "NPCSpokenTo": "speaks_with", "BeaconAwakened": "awakens",
                "CreatureDamaged": "attacks", "PlayerGuarded": "guards", "PlayerDodged": "evades",
                "CreatureReawakened": "reawakens",
            }.get(event_type)
            rationale = {
                "ResourceGathered": f"{PLAYER_NAMES[player_id]} gathered a nearby lumen reed patch.",
                "NPCSpokenTo": f"{PLAYER_NAMES[player_id]} chose to speak with Mara.",
                "BeaconAwakened": f"{PLAYER_NAMES[player_id]} offered three lumen reeds to awaken the listening beacon.",
                "CreatureDamaged": f"{PLAYER_NAMES[player_id]} fought the nearby Mossling; the creature retaliated.",
                "PlayerGuarded": f"{PLAYER_NAMES[player_id]} raised a guard against the nearby Mossling.",
                "PlayerDodged": f"{PLAYER_NAMES[player_id]} sidestepped the nearby Mossling's attack line.",
                "CreatureReawakened": f"{PLAYER_NAMES[player_id]} called the Mossling back from its resting place.",
            }.get(event_type)
            if event_type == "PlayerMoved":
                rationale = f"{PLAYER_NAMES[player_id]} moved through the valley to {payload['x']},{payload['z']}."
            assert rationale is not None
            if event_type == "PlayerMoved" and input_sequence is not None:
                payload = {**payload, "tick": input_sequence}
            event_contract = {"event_id": event_id, "event_type": event_type, "schema_version": 1,
                              "occurred_at": occurred_at, "actor_id": player_id, "source_kind": "player_action",
                              "source_identifier": source_identifier, "rationale": rationale,
                              "subject_id": player_id, "object_id": object_id}
            self.contracts.validate_event(event_contract, relation_for_event)
            db.execute(
                """INSERT INTO world_events(
                       event_id, schema_version, occurred_at, event_type, actor_id,
                       source_kind, source_identifier, rationale, subject_id, object_id, payload_json
                   ) VALUES (?, 1, ?, ?, ?, 'player_action', ?, ?, ?, ?, ?)""",
                (event_id, occurred_at, event_type, player_id, source_identifier, rationale, player_id, object_id,
                 json.dumps(payload, separators=(",", ":"), sort_keys=True)),
            )
            if relation_for_event is not None:
                db.execute(
                    """INSERT INTO knowledge_relationships(
                           relationship_id, relation_type, source_entity_id,
                           target_entity_id, recorded_at, source_event_id,
                           source_kind, source_identifier, rationale
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (str(uuid.uuid5(uuid.NAMESPACE_URL, f"atlas:event:{event_id}")), relation_for_event,
                     event_contract["subject_id"], event_contract["object_id"], occurred_at, event_id,
                     event_contract["source_kind"], source_identifier, rationale),
                )
            new_shared, new_personal = _split_state(state)
            updated = db.execute(
                "UPDATE world_state SET version = ?, state_json = ? WHERE singleton = 1 AND version = ?",
                (row["version"] + 1, json.dumps(new_shared, separators=(",", ":")), row["version"]),
            ).rowcount
            if updated != 1:
                raise RuntimeError("world projection version changed during command")
            new_tick = input_sequence if event_type == "PlayerMoved" and input_sequence is not None else int(profile["last_tick"])
            db.execute("UPDATE player_states SET state_json = ?, last_tick = ? WHERE player_id = ?",
                       (json.dumps(new_personal, separators=(",", ":")), new_tick, player_id))
            db.execute("COMMIT")
            if event_type == "PlayerMoved":
                runtime["active_input"] = requested_input
                runtime["active_run"] = requested_run
                self._record_history(player_id, new_tick, now, state["player"])
            elif event_type == "PlayerDodged":
                runtime["active_input"] = {"x": 0.0, "z": 0.0}
                runtime["active_run"] = False
            result = {"event_id": event_id, "event_type": event_type, "at": occurred_at, "detail": payload}
            if event_type == "PlayerMoved" and input_sequence is not None:
                result["acknowledged_sequence"] = input_sequence
                runtime["last_tick"] = input_sequence
                runtime["ack_cache"][input_sequence] = result
                if len(runtime["ack_cache"]) > 64:
                    del runtime["ack_cache"][min(runtime["ack_cache"])]
            return result
        except Exception:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise
        finally:
            db.close()

    def rebuild_projection(self) -> dict[str, Any]:
        """Rebuild shared and per-player projections from immutable events."""
        db = self.connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            base = initial_state()
            shared, _ = _split_state(base)
            personal_by_player: dict[str, dict[str, Any]] = {}
            appearance_by_player: dict[str, dict[str, Any]] = {}
            last_ticks = {player_id: 0 for player_id in PLAYER_ENTITY_IDS}
            for player_id in PLAYER_ENTITY_IDS:
                row = db.execute(
                    "SELECT appearance_json FROM player_profiles WHERE player_id = ?", (player_id,)
                ).fetchone()
                if row is None:
                    raise ValueError("Player profile is unavailable during projection rebuild.")
                appearance_by_player[player_id] = json.loads(row["appearance_json"])
                personal_by_player[player_id] = _initial_player_projection(player_id)
            events = db.execute(
                """SELECT event_id, actor_id, event_type, occurred_at, source_kind,
                          source_identifier, rationale, subject_id, object_id, payload_json
                   FROM world_events ORDER BY sequence"""
            ).fetchall()
            for event in events:
                player_id = event["actor_id"] if event["actor_id"] in personal_by_player else PLAYER_ENTITY_ID
                payload = json.loads(event["payload_json"])
                if event["event_type"] == "EntityCreated":
                    entity = payload.get("entity")
                    if not isinstance(entity, dict):
                        raise ValueError("EntityCreated history entry has no entity payload.")
                    self.contracts.validate_entity(entity)
                    attributes = {key: value for key, value in entity.items()
                                  if key not in {"id", "type", "created_at"}}
                    db.execute(
                        """INSERT OR IGNORE INTO atlas_entities(
                               entity_id, entity_type, created_at, attributes_json
                           ) VALUES (?, ?, ?, ?)""",
                        (entity["id"], entity["type"], entity["created_at"],
                         json.dumps(attributes, separators=(",", ":"), sort_keys=True)),
                    )
                relation_type = {
                    "ResourceGathered": "gathers", "NPCSpokenTo": "speaks_with",
                    "BeaconAwakened": "awakens", "CreatureDamaged": "attacks",
                    "PlayerGuarded": "guards", "PlayerDodged": "evades",
                    "CreatureReawakened": "reawakens",
                }.get(event["event_type"])
                if event["event_type"] == "RelationshipEstablished":
                    relation_type = payload.get("relationship_type")
                if relation_type is not None:
                    source_type_row = db.execute(
                        "SELECT entity_type FROM atlas_entities WHERE entity_id = ?", (event["subject_id"],)
                    ).fetchone()
                    target_type_row = db.execute(
                        "SELECT entity_type FROM atlas_entities WHERE entity_id = ?", (event["object_id"],)
                    ).fetchone()
                    if source_type_row is None or target_type_row is None:
                        raise ValueError("World history relationship references a missing graph entity.")
                    self.contracts.validate_relationship(relation_type, source_type_row["entity_type"],
                                                        target_type_row["entity_type"])
                    db.execute(
                        """INSERT OR IGNORE INTO knowledge_relationships(
                               relationship_id, relation_type, source_entity_id,
                               target_entity_id, recorded_at, source_event_id,
                               source_kind, source_identifier, rationale
                           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (str(uuid.uuid5(uuid.NAMESPACE_URL, f"atlas:event:{event['event_id']}")),
                         relation_type, event["subject_id"], event["object_id"], event["occurred_at"],
                         event["event_id"], event["source_kind"], event["source_identifier"], event["rationale"]),
                    )
                state = {**shared, **personal_by_player[player_id]}
                replay_event(state, event["event_type"], payload)
                shared, personal_by_player[player_id] = _split_state(state)
                if event["event_type"] == "PlayerMoved" and isinstance(payload.get("tick"), int):
                    last_ticks[player_id] = max(last_ticks[player_id], payload["tick"])
            db.execute("UPDATE world_state SET version = ?, state_json = ? WHERE singleton = 1",
                       (len(events), json.dumps(shared, separators=(",", ":"))))
            for player_id, personal in personal_by_player.items():
                db.execute("UPDATE player_states SET state_json = ?, last_tick = ? WHERE player_id = ?",
                           (json.dumps(personal, separators=(",", ":")), last_ticks[player_id], player_id))
            db.execute("COMMIT")
            return {
                **shared,
                **personal_by_player[PLAYER_ENTITY_ID],
                "appearance": appearance_by_player[PLAYER_ENTITY_ID],
            }
        except Exception:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise
        finally:
            db.close()


class SessionCapacityError(ValueError):
    """Raised when both local player seats are occupied."""
