import math
import json
import tempfile
import unittest
from datetime import datetime, timezone
from uuid import uuid4
from pathlib import Path

from atlas_server.contracts import AtlasContracts
from atlas_server.history import EntityHistory, HitboxSnapshot, validate_melee_hit
from atlas_server.store import WorldStore
from atlas_server.world import (
    COYOTE_SECONDS, JUMP_BUFFER_SECONDS, JUMP_GRAVITY, JUMP_SPEED,
    CREATOR_ENTITY_ID, PLAYER_ENTITY_ID, PLAYER_ENTITY_IDS, REGION_ENTITY_ID,
    WORLD_ENTITY_IDS, WORLD_OBSTACLES, TERRAIN,
    apply_action, initial_state, walkable_position,
)


ROOT = Path(__file__).resolve().parents[1]
SPECS = ROOT / "specs" / "atlas" / "specs"


class MovementSequenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = WorldStore(Path(self.temp.name) / "world.sqlite3", AtlasContracts(SPECS))

    def tearDown(self):
        self.temp.cleanup()

    def move(self, sequence, direction):
        return self.store.command({"type": "move", "sequence": sequence,
                                   "input": {"x": direction, "z": 0}, "run": False})

    def test_retry_of_committed_input_returns_same_ack_without_duplicate_event(self):
        first = self.move(1, 1)
        duplicate = self.move(1, 1)
        self.assertEqual(duplicate, first)
        self.assertEqual(self.store.last_input_sequence, 1)
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM world_events").fetchone()[0], 1)

    def test_skipped_sequence_is_allowed_and_old_uncached_sequence_is_rejected(self):
        self.move(1, 1)
        latest = self.move(3, 0)
        self.assertEqual(latest["acknowledged_sequence"], 3)
        with self.assertRaisesRegex(ValueError, "stale"):
            self.move(2, -1)

    def test_fixed_tick_batch_applies_each_frame_and_retries_idempotently(self):
        frames = [
            {"sequence": 1, "input": {"x": 1, "z": 0}, "run": False},
            {"sequence": 2, "input": {"x": 1, "z": 0}, "run": False},
            {"sequence": 3, "input": {"x": 0, "z": 0}, "run": False},
        ]
        command = {"type": "move", "sequence": 3, "frames": frames}
        first = self.store.command(command)
        self.assertEqual(first["acknowledged_sequence"], 3)
        state, events = self.store.read()
        self.assertAlmostEqual(state["player"]["x"], first["detail"]["x"], places=4)
        self.assertEqual(len(events), 1)
        self.assertEqual(self.store.command(command), first)
        self.assertEqual(len(self.store.read()[1]), 1)

    def test_fixed_tick_batch_rejects_sequence_gaps(self):
        command = {"type": "move", "sequence": 2, "frames": [
            {"sequence": 1, "input": {"x": 1, "z": 0}, "run": False},
            {"sequence": 2, "input": {"x": 1, "z": 0}, "run": False},
        ]}
        self.store.command(command)
        invalid = {"type": "move", "sequence": 4, "frames": [
            {"sequence": 4, "input": {"x": 0, "z": 1}, "run": False},
        ]}
        with self.assertRaisesRegex(ValueError, "gap"):
            self.store.command(invalid)

    def test_high_ping_tick_is_bounded_and_integrated_without_tunneling_steps(self):
        state = initial_state()
        state, _, _ = apply_action(state, {"type": "move", "input": {"x": 1, "z": 0},
                                           "_sim_input": {"x": 1, "z": 0}, "_sim_run": False, "dt": .25})
        self.assertTrue(math.isfinite(state["player"]["x"]))
        self.assertLess(state["player"]["x"] - 3, 2.5 * .25)

    def test_server_movement_matches_shared_browser_fixed_tick_contract(self):
        fixture = json.loads((ROOT / "tests" / "fixtures" / "movement-contract.json").read_text())
        state = initial_state()
        for segment in fixture["segments"]:
            for _ in range(segment["ticks"]):
                state, _, _ = apply_action(state, {
                    "type": "move", "input": segment["input"], "run": segment["run"],
                    "_sim_input": segment["input"], "_sim_run": segment["run"],
                    "dt": 1 / fixture["fixed_hz"],
                })
        player = state["player"]
        self.assertLess(math.hypot(player["x"] - fixture["expected"]["position"]["x"],
                                   player["y"] - fixture["expected"]["position"]["z"]), 1e-9)
        self.assertLess(math.hypot(player["vx"] - fixture["expected"]["velocity"]["x"],
                                   player["vz"] - fixture["expected"]["velocity"]["z"]), 1e-9)

    def test_server_jump_matches_shared_controller_contract(self):
        fixture = json.loads((ROOT / "tests" / "fixtures" / "movement-contract.json").read_text())
        jump = fixture["jump"]
        self.assertEqual((JUMP_SPEED, JUMP_GRAVITY, JUMP_BUFFER_SECONDS, COYOTE_SECONDS),
                         (jump["speed"], jump["gravity"], jump["buffer_seconds"], jump["coyote_seconds"]))
        state = initial_state()
        peak, apex_tick, landing_tick = 0.0, None, None
        for tick in range(1, 61):
            state, _, detail = apply_action(state, {
                "type": "move", "input": {"x": 0, "z": 0}, "run": False,
                "jump": tick == 1, "_sim_input": {"x": 0, "z": 0},
                "_sim_run": False, "dt": 1 / fixture["fixed_hz"],
            })
            height = state["player"]["height"]
            if height > peak:
                peak, apex_tick = height, tick
            if tick > 1 and detail["grounded"] and landing_tick is None:
                landing_tick = tick
        self.assertEqual(apex_tick, jump["expected_apex_tick"])
        self.assertAlmostEqual(peak, jump["expected_apex_height"], places=12)
        self.assertEqual(landing_tick, jump["expected_landing_tick"])
        self.assertEqual(state["player"]["height"], 0.0)
        self.assertTrue(state["player"]["grounded"])
        self.assertEqual(state["player"]["vy"], 0.0)

    def test_server_terrain_footprint_matches_shared_collision_contract(self):
        fixture = json.loads((ROOT / "tests" / "fixtures" / "movement-contract.json").read_text())
        for sample in fixture["walkability"]:
            self.assertEqual(walkable_position(sample["x"], sample["z"]), sample["walkable"])

    def test_server_character_sandbox_uses_only_flat_walkable_ground(self):
        fixture = json.loads((ROOT / "tests" / "fixtures" / "movement-contract.json").read_text())
        self.assertEqual(len(TERRAIN), 14)
        self.assertTrue(all(len(row) == 40 for row in TERRAIN))
        for sample in fixture["obstacleCollisions"]:
            self.assertEqual(walkable_position(sample["x"], sample["z"], obstacles=[sample["obstacle"]]),
                             sample["walkable"])
        self.assertEqual(WORLD_OBSTACLES, [])
        self.assertTrue(all(set(row) == {"."} for row in TERRAIN))

    def test_recent_server_recorded_position_can_rewind_a_late_melee_attack(self):
        import time
        self.store._last_input_sequence = 7
        self.store._record_history(7, time.monotonic(), {"x": 11.5, "y": 9.0})
        result = self.store.command({"type": "attack", "target": "mossling", "rewind_sequence": 7})
        self.assertEqual(result["event_type"], "CreatureDamaged")
        self.assertTrue(result["detail"]["rewind_applied"])

    def test_stale_attack_history_falls_back_to_current_authoritative_position(self):
        import time
        self.store._player_history = EntityHistory(max_seconds=2.0, max_samples=120)
        self.store._target_history = EntityHistory(max_seconds=2.0, max_samples=120)
        self.store._last_input_sequence = 7
        self.store._record_history(7, time.monotonic() - .75, {"x": 11.5, "y": 9.0})
        with self.assertRaisesRegex(ValueError, "closer"):
            self.store.command({"type": "attack", "target": "mossling", "rewind_sequence": 7})

    def test_local_sessions_claim_two_distinct_players_and_reject_a_third(self):
        first = self.store.create_session()
        second = self.store.create_session()
        self.assertNotEqual(first["session_token"], second["session_token"])
        self.assertEqual({first["player_id"], second["player_id"]}, set(PLAYER_ENTITY_IDS))
        self.assertEqual(self.store.player_for_session(first["session_token"]), first["player_id"])
        self.assertIsNone(self.store.player_for_session("unknown-session"))
        with self.assertRaisesRegex(ValueError, "Both local traveler seats"):
            self.store.create_session()

    def test_each_player_has_independent_ticks_position_and_event_actor(self):
        frames_one = [{"sequence": n, "input": {"x": 1, "z": 0}, "run": False} for n in (1, 2, 3)]
        frames_two = [{"sequence": n, "input": {"x": 0, "z": -1}, "run": False} for n in (1, 2, 3)]
        result_one = self.store.command({"type": "move", "sequence": 3, "frames": frames_one}, PLAYER_ENTITY_IDS[0])
        result_two = self.store.command({"type": "move", "sequence": 3, "frames": frames_two}, PLAYER_ENTITY_IDS[1])
        self.assertEqual(result_one["acknowledged_sequence"], 3)
        self.assertEqual(result_two["acknowledged_sequence"], 3)
        self.assertEqual(self.store.last_input_sequence_for(PLAYER_ENTITY_IDS[0]), 3)
        self.assertEqual(self.store.last_input_sequence_for(PLAYER_ENTITY_IDS[1]), 3)
        first_state, events = self.store.read(PLAYER_ENTITY_IDS[0])
        self_state, _ = self.store.read(PLAYER_ENTITY_IDS[1])
        positions = {player["id"]: player for player in first_state["players"]}
        self.assertGreater(positions[PLAYER_ENTITY_IDS[0]]["x"], 3.0)
        self.assertLess(positions[PLAYER_ENTITY_IDS[1]]["y"], 10.0)
        self.assertEqual(self_state["player"]["x"], positions[PLAYER_ENTITY_IDS[1]]["x"])
        self.assertEqual([event["actor_id"] for event in events], list(PLAYER_ENTITY_IDS))

    def test_shared_gather_is_claimed_once_but_inventory_belongs_to_actor(self):
        with self.store.connect() as db:
            row = db.execute("SELECT state_json FROM player_states WHERE player_id = ?", (PLAYER_ENTITY_IDS[0],)).fetchone()
            personal = json.loads(row["state_json"])
            personal["player"].update(x=5.0, y=5.8)
            db.execute("UPDATE player_states SET state_json = ? WHERE player_id = ?",
                       (json.dumps(personal), PLAYER_ENTITY_IDS[0]))
        self.store.command({"type": "interact", "target": "reed-west"}, PLAYER_ENTITY_IDS[0])
        first, _ = self.store.read(PLAYER_ENTITY_IDS[0])
        second, _ = self.store.read(PLAYER_ENTITY_IDS[1])
        self.assertEqual(first["inventory"]["lumen_reed"], 1)
        self.assertEqual(second["inventory"]["lumen_reed"], 0)
        self.assertIn("reed-west", first["gathered"])

    def test_ontology_world_relationships_are_persisted_and_explainable(self):
        graph = self.store.query_knowledge(relation_type="located_in")
        self.assertEqual(len(graph["relationships"]), 4)
        self.assertTrue(all(edge["event_id"] is None for edge in graph["relationships"]))
        self.assertTrue(all(edge["rationale"] for edge in graph["relationships"]))
        self.assertEqual({entity["type"] for entity in graph["entities"]}, {"Player", "NPC", "Creature", "Region"})

    def test_action_relationship_and_memory_survive_reopen_and_projection_rebuild(self):
        player_id = PLAYER_ENTITY_IDS[0]
        resource_id = WORLD_ENTITY_IDS["reed-west"]
        with self.store.connect() as db:
            row = db.execute("SELECT state_json FROM player_states WHERE player_id = ?", (player_id,)).fetchone()
            personal = json.loads(row["state_json"])
            personal["player"].update(x=5.0, y=5.8)
            db.execute("UPDATE player_states SET state_json = ? WHERE player_id = ?",
                       (json.dumps(personal), player_id))

        event = self.store.command({"type": "interact", "target": "reed-west"}, player_id)
        graph = self.store.query_knowledge(source_id=player_id, target_id=resource_id, relation_type="gathers")
        self.assertEqual(len(graph["relationships"]), 1)
        edge = graph["relationships"][0]
        self.assertEqual(edge["event_id"], event["event_id"])
        self.assertEqual(edge["actor_id"], player_id)
        self.assertIn("gathered", edge["rationale"])

        history = self.store.query_memory(entity_id=resource_id)
        self.assertEqual([item["event_id"] for item in history], [event["event_id"]])
        self.assertEqual(history[0]["rationale"], edge["rationale"])

        reopened = WorldStore(self.store.path, AtlasContracts(SPECS))
        reopened.rebuild_projection()
        restored = reopened.query_knowledge(source_id=player_id, target_id=resource_id, relation_type="gathers")
        self.assertEqual(restored["relationships"][0]["event_id"], event["event_id"])
        self.assertEqual(reopened.query_memory(entity_id=resource_id)[0]["event_id"], event["event_id"])

    def test_creator_authored_entity_relationship_and_explanation_are_atomic_and_durable(self):
        source = {"kind": "creator_edit", "identifier": str(uuid4())}
        npc = {"id": str(uuid4()), "type": "NPC",
               "created_at": datetime.now(timezone.utc).isoformat(), "name": "Ilyra the Cartographer"}
        created = self.store.create_entity(
            npc, source_kind=source["kind"], source_identifier=source["identifier"],
            rationale="Added Ilyra to provide a route into the eastern village.",
        )
        linked = self.store.create_relationship(
            "located_in", npc["id"], REGION_ENTITY_ID, source_kind=source["kind"],
            source_identifier=source["identifier"],
            rationale="Ilyra works from the Valley of First Light while mapping its roads.",
        )
        analytics_first_page = self.store.query_analytics(limit=1)
        self.assertEqual(analytics_first_page["window"]["event_count"], 1)
        self.assertTrue(analytics_first_page["window"]["has_more"])
        analytics_second_page = self.store.query_analytics(
            after_sequence=analytics_first_page["window"]["through_sequence"], limit=1)
        self.assertEqual(analytics_second_page["activity"]["events_by_type"], {"RelationshipEstablished": 1})
        self.assertFalse(analytics_second_page["window"]["has_more"])
        explanation = self.store.query_knowledge(
            source_id=npc["id"], target_id=REGION_ENTITY_ID, relation_type="located_in")
        edge = next(edge for edge in explanation["relationships"] if edge["event_id"] == linked["event_id"])
        self.assertEqual(edge["actor_id"], CREATOR_ENTITY_ID)
        self.assertEqual(edge["source"], source)
        self.assertEqual(edge["rationale"], linked["rationale"])
        self.assertIn(npc, [{"id": entity["id"], "type": entity["type"],
                             "created_at": entity["created_at"], **entity["attributes"]}
                            for entity in explanation["entities"]])

        with self.assertRaisesRegex(ValueError, "already exists"):
            self.store.create_entity(npc, source_kind=source["kind"], source_identifier=source["identifier"],
                                     rationale="Duplicate entity")
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.store.create_relationship("located_in", npc["id"], REGION_ENTITY_ID,
                                           source_kind=source["kind"], source_identifier=source["identifier"],
                                           rationale="Duplicate relationship")
        with self.assertRaises(ValueError):
            self.store.create_relationship("not_declared", npc["id"], REGION_ENTITY_ID,
                                           source_kind=source["kind"], source_identifier=source["identifier"],
                                           rationale="Invalid ontology edge")
        malformed = {**npc, "id": str(uuid4()), "type": "UnregisteredType"}
        with self.assertRaisesRegex(ValueError, "not registered"):
            self.store.create_entity(malformed, source_kind=source["kind"],
                                     source_identifier=source["identifier"], rationale="Invalid entity type")
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM world_events").fetchone()[0], 2)
            import sqlite3
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("UPDATE knowledge_relationships SET rationale = 'tampered' WHERE source_event_id = ?",
                           (linked["event_id"],))

        reopened = WorldStore(self.store.path, AtlasContracts(SPECS))
        rebuilt = reopened.rebuild_projection()
        self.assertTrue(rebuilt)
        restored = reopened.query_knowledge(source_id=npc["id"], target_id=REGION_ENTITY_ID,
                                            relation_type="located_in")
        self.assertEqual(len(restored["relationships"]), 1)
        self.assertEqual(restored["relationships"][0]["event_id"], linked["event_id"])
        self.assertEqual([event["event_id"] for event in reopened.query_memory(entity_id=npc["id"])],
                         [created["event_id"], linked["event_id"]])

    def test_other_traveler_is_a_shared_solid_movement_collider(self):
        other_id = PLAYER_ENTITY_IDS[1]
        with self.store.connect() as db:
            row = db.execute("SELECT state_json FROM player_states WHERE player_id = ?", (other_id,)).fetchone()
            personal = json.loads(row["state_json"])
            personal["player"].update(x=4.2, y=10.0, vx=0.0, vz=0.0)
            db.execute("UPDATE player_states SET state_json = ? WHERE player_id = ?",
                       (json.dumps(personal), other_id))
        for start in (1, 33, 65):
            frames = [{"sequence": n, "input": {"x": 1, "z": 0}, "run": False}
                      for n in range(start, start + 32)]
            self.store.command({"type": "move", "sequence": start + 31, "frames": frames}, PLAYER_ENTITY_IDS[0])
        first, _ = self.store.read(PLAYER_ENTITY_IDS[0])
        self.assertLessEqual(first["player"]["x"], 3.81)

    def test_player_state_and_tick_survive_store_reopen_and_projection_rebuild(self):
        player_id = PLAYER_ENTITY_IDS[1]
        frames = [{"sequence": n, "input": {"x": 1, "z": 0}, "run": False} for n in (1, 2)]
        self.store.command({"type": "move", "sequence": 2, "frames": frames}, player_id)
        saved, _ = self.store.read(player_id)
        with self.store.connect() as db:
            db.execute("UPDATE player_states SET last_tick = 0 WHERE player_id = ?", (player_id,))
        rebuilt = self.store.rebuild_projection()
        self.assertEqual(rebuilt["gathered"], saved["gathered"])
        self.assertEqual(self.store.last_input_sequence_for(player_id), 2)
        self.store = WorldStore(Path(self.temp.name) / "world.sqlite3", AtlasContracts(SPECS))
        reopened, _ = self.store.read(player_id)
        for coordinate in ("x", "y", "vx", "vz"):
            self.assertAlmostEqual(reopened["player"][coordinate], saved["player"][coordinate], places=12)
        self.assertEqual(self.store.last_input_sequence_for(player_id), 2)


class HitboxRewindTests(unittest.TestCase):
    def setUp(self):
        self.history = EntityHistory(max_seconds=2.0, max_samples=120)
        self.history.record(HitboxSnapshot(10.0, 0, 0, 0, .35, 1.8, 0))
        self.history.record(HitboxSnapshot(10.1, 1, 0, 0, .45, 1.8, .2))
        self.history.record(HitboxSnapshot(10.2, 2, 0, 0, .35, 1.8, .4))

    def test_rewind_interpolates_position_dimensions_and_rotation(self):
        sample = self.history.rewind(10.05)
        self.assertIsNotNone(sample)
        self.assertAlmostEqual(sample.x, .5)
        self.assertAlmostEqual(sample.radius, .4)
        self.assertAlmostEqual(sample.yaw, .1)

    def test_delayed_attack_uses_target_hitbox_at_attack_time(self):
        rewound = self.history.rewind(10.05)
        self.assertTrue(validate_melee_hit((0, 0, 0), rewound, reach=.3))
        current = self.history.rewind(10.2)
        self.assertFalse(validate_melee_hit((-.7, 0, 0), current, reach=.3))

    def test_rejects_timestamps_outside_recorded_window_and_invalid_snapshots(self):
        self.assertIsNone(self.history.rewind(9.0))
        self.assertIsNone(self.history.rewind(10.5))
        with self.assertRaises(ValueError):
            self.history.record(HitboxSnapshot(10.15, 0, 0, 0, .3, 1.8))


if __name__ == "__main__":
    unittest.main()
