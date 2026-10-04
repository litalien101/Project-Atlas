import json
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch
from uuid import uuid4

from atlas_server.contracts import AtlasContracts
from atlas_server.server import Handler
from atlas_server.store import WorldStore
from atlas_server.world import CREATOR_ENTITY_ID, PLAYER_ENTITY_IDS, REGION_ENTITY_ID, initial_state

ROOT = Path(__file__).resolve().parents[1]
SPECS = ROOT / "specs" / "atlas" / "specs"


class SessionApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = WorldStore(Path(self.temp.name) / "world.sqlite3", AtlasContracts(SPECS))
        self.asset_root = Path(self.temp.name) / "assets"
        self.asset_root.mkdir()
        handler = type("BoundHandler", (Handler,), {"store": self.store, "asset_root": self.asset_root})
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(timeout=2)
        self.server.server_close()
        self.temp.cleanup()

    def request(self, path, method="GET", body=None, token=None):
        headers = {"Accept": "application/json"}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        if token is not None:
            headers["X-Atlas-Session"] = token
        req = Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with urlopen(req, timeout=3) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def raw_request(self, path):
        req = Request(self.base + path, headers={"Accept": "*/*"})
        try:
            with urlopen(req, timeout=3) as response:
                return response.status, response.headers, response.read()
        except HTTPError as error:
            return error.code, error.headers, error.read()

    def test_asset_route_serves_models_and_relative_resources(self):
        model_directory = self.asset_root / "base character"
        model_directory.mkdir()
        model_bytes = b'{"asset":{"version":"2.0"}}'
        resource_bytes = b"model-resource"
        binary_model_bytes = b"glb-resource"
        texture_bytes = b"png-resource"
        (model_directory / "character.gltf").write_bytes(model_bytes)
        (model_directory / "character.bin").write_bytes(resource_bytes)
        (model_directory / "character.glb").write_bytes(binary_model_bytes)
        (model_directory / "albedo.png").write_bytes(texture_bytes)

        status, headers, body = self.raw_request("/assets/base%20character/character.gltf")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "model/gltf+json")
        self.assertEqual(headers["Cache-Control"], "public, max-age=3600")
        self.assertEqual(body, model_bytes)

        status, headers, body = self.raw_request("/assets/base%20character/character.bin")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "application/octet-stream")
        self.assertEqual(body, resource_bytes)

        status, headers, body = self.raw_request("/assets/base%20character/character.glb")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "model/gltf-binary")
        self.assertEqual(body, binary_model_bytes)

        status, headers, body = self.raw_request("/assets/base%20character/albedo.png")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "image/png")
        self.assertEqual(body, texture_bytes)

    def test_asset_route_rejects_traversal_symlink_and_unsupported_files(self):
        private_file = Path(self.temp.name) / "outside.png"
        private_file.write_bytes(b"private")
        (self.asset_root / "escape.png").symlink_to(private_file)
        (self.asset_root / "script.js").write_text("alert(1)")

        for path in ("/assets/%2e%2e/outside.png", "/assets/escape.png", "/assets/script.js"):
            with self.subTest(path=path):
                status, _, _ = self.raw_request(path)
                self.assertEqual(status, 404)

    def test_api_requires_session_and_binds_events_to_server_resolved_player(self):
        status, body = self.request("/api/state")
        self.assertEqual(status, 401)
        status, session = self.request("/api/session", method="POST")
        self.assertEqual(status, 201)
        self.assertIn(session["player_id"], PLAYER_ENTITY_IDS)
        status, state = self.request("/api/state", token=session["session_token"])
        self.assertEqual(status, 200)
        self.assertEqual(state["active_player"]["id"], session["player_id"])
        status, _ = self.request("/api/action", method="POST", body={
            "type": "move", "sequence": 1,
            "frames": [{"sequence": 1, "input": {"x": 1, "z": 0}, "run": False}],
        }, token=session["session_token"])
        self.assertEqual(status, 200)
        _, recent = self.store.read(session["player_id"])
        self.assertEqual(recent[-1]["actor_id"], session["player_id"])

    def test_action_api_rejects_forged_server_fields_without_mutating_state_or_events(self):
        _, session = self.request("/api/session", method="POST")
        token = session["session_token"]
        before_state, _ = self.store.read(session["player_id"])
        with self.store.connect() as db:
            before_events = db.execute("SELECT COUNT(*) FROM world_events").fetchone()[0]

        status, error = self.request("/api/action", method="POST", body={
            "type": "attack",
            "target": "mossling",
            "_attack_origin": {"x": 12.0, "y": 9.0},
        }, token=token)
        self.assertEqual(status, 422)
        self.assertIn("Unsupported action field", error["error"])

        after_state, _ = self.store.read(session["player_id"])
        with self.store.connect() as db:
            after_events = db.execute("SELECT COUNT(*) FROM world_events").fetchone()[0]
        self.assertEqual(after_events, before_events)
        for field in ("inventory", "player_health", "journal", "mossling_health", "mossling_defeated"):
            self.assertEqual(after_state[field], before_state[field])

        status, error = self.request("/api/action", method="POST", body={
            "type": "move", "sequence": 1,
            "frames": [{"sequence": 1, "input": {"x": 0, "z": 0}, "run": False}],
            "player_id": PLAYER_ENTITY_IDS[1],
        }, token=token)
        self.assertEqual(status, 422)
        self.assertIn("Unsupported action field", error["error"])
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM world_events").fetchone()[0], before_events)

    def test_action_api_still_applies_server_resolved_rewind_context(self):
        import time
        _, session = self.request("/api/session", method="POST")
        player_id = session["player_id"]
        self.store._last_input_sequence = 7
        self.store._record_history(7, time.monotonic(), {"x": 11.5, "y": 9.0})

        status, result = self.request("/api/action", method="POST", body={
            "type": "attack", "target": "mossling", "rewind_sequence": 7,
        }, token=session["session_token"])
        self.assertEqual(status, 200)
        self.assertEqual(result["event_type"], "CreatureDamaged")
        self.assertTrue(result["detail"]["rewind_applied"])
        _, events = self.store.read(player_id)
        self.assertEqual(events[-1]["type"], "CreatureDamaged")

    def test_knowledge_and_memory_queries_require_a_session_and_return_provenance(self):
        status, _ = self.request("/api/knowledge?type=located_in")
        self.assertEqual(status, 401)
        status, session = self.request("/api/session", method="POST")
        self.assertEqual(status, 201)

        status, graph = self.request("/api/knowledge?type=located_in", token=session["session_token"])
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(graph["relationships"]), 4)
        self.assertTrue(all(edge["rationale"] for edge in graph["relationships"]))

        status, history = self.request("/api/memory?limit=5", token=session["session_token"])
        self.assertEqual(status, 200)
        self.assertIsInstance(history, list)

        status, analytics = self.request("/api/analytics?limit=5", token=session["session_token"])
        self.assertEqual(status, 200)
        self.assertIn("resources", analytics)
        self.assertIn("timeline", analytics)
        self.assertTrue(analytics["limitations"])

        status, error = self.request("/api/knowledge?type=undeclared", token=session["session_token"])
        self.assertEqual(status, 422)
        self.assertIn("ontology", error["error"])

    def test_creator_api_persists_a_world_entity_and_explainable_relationship(self):
        npc_id = str(uuid4())
        source = {"kind": "creator_edit", "identifier": str(uuid4())}
        status, creation = self.request("/api/entities", method="POST", body={
            "entity": {"id": npc_id, "type": "NPC",
                       "created_at": datetime.now(timezone.utc).isoformat(),
                       "name": "Ilyra the Cartographer"},
            "source": source,
            "rationale": "Add a cartographer to explain the eastern road network.",
        })
        self.assertEqual(status, 201)
        self.assertEqual(creation["actor_id"], CREATOR_ENTITY_ID)

        status, link = self.request("/api/relationships", method="POST", body={
            "type": "located_in", "source_id": npc_id, "target_id": REGION_ENTITY_ID,
            "source": source,
            "rationale": "The cartographer is based in the Valley of First Light.",
        })
        self.assertEqual(status, 201)

        status, graph = self.request(
            f"/api/knowledge?source={npc_id}&target={REGION_ENTITY_ID}&type=located_in")
        self.assertEqual(status, 401)
        session_status, session = self.request("/api/session", method="POST")
        self.assertEqual(session_status, 201)
        status, graph = self.request(
            f"/api/knowledge?source={npc_id}&target={REGION_ENTITY_ID}&type=located_in",
            token=session["session_token"])
        self.assertEqual(status, 200)
        edge = next(item for item in graph["relationships"] if item["event_id"] == link["event_id"])
        self.assertEqual(edge["actor_id"], CREATOR_ENTITY_ID)
        self.assertEqual(edge["source"], source)
        self.assertEqual(edge["rationale"], link["rationale"])

        status, explanation = self.request(
            f"/api/reasoning?event={link['event_id']}", token=session["session_token"])
        self.assertEqual(status, 200)
        self.assertEqual(explanation["kind"], "authored_event_provenance")
        self.assertEqual(explanation["evidence"][0]["id"], link["event_id"])
        self.assertIsNone(explanation["confidence"])
        self.assertFalse(explanation["truth_record_created"])

        status, error = self.request("/api/relationships", method="POST", body={
            "type": "located_in", "source_id": npc_id, "target_id": REGION_ENTITY_ID,
            "source": source, "rationale": "Duplicate edge",
        })
        self.assertEqual(status, 422)
        self.assertIn("already exists", error["error"])
        self.assertEqual(len(self.store.query_memory(entity_id=npc_id)), 2)

    def test_policy_evaluation_is_persisted_and_never_changes_world_state(self):
        status, session = self.request("/api/session", method="POST")
        self.assertEqual(status, 201)
        actor_id = session["player_id"]
        simulation = self.store.run_simulation(
            {"rule": "beacon.lumen_reed_cost", "value": 2}, actor_id)
        with self.store.connect() as db:
            event_count_before = db.execute("SELECT COUNT(*) FROM world_events").fetchone()[0]
            projection_before = db.execute("SELECT version, state_json FROM world_state").fetchone()
            projection_before = (projection_before["version"], projection_before["state_json"])

        status, result = self.request("/api/policy/evaluations", method="POST",
                                      body={"simulation_id": simulation["simulation_id"]},
                                      token=session["session_token"])
        self.assertEqual(status, 201)
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["world_change_applied"])
        self.assertEqual(self.request(f"/api/policy/evaluations/{result['evaluation_id']}",
                                      token=session["session_token"])[1], result)
        status, decision = self.request("/api/decisions", method="POST", body={
            "simulation_id": simulation["simulation_id"], "evaluation_id": result["evaluation_id"]},
            token=session["session_token"])
        self.assertEqual(status, 201)
        self.assertEqual(decision["recommended_output"], "reject")
        self.assertEqual(decision["status"], "blocked_by_policy")
        self.assertFalse(decision["world_change_applied"])
        self.assertEqual(self.request(f"/api/decisions/{decision['decision_id']}",
                                      token=session["session_token"])[1], decision)
        mismatch_status, _ = self.request("/api/decisions", method="POST", body={
            "simulation_id": simulation["simulation_id"], "evaluation_id": "00000000-0000-4000-8000-000000000000"},
            token=session["session_token"])
        self.assertEqual(mismatch_status, 422)
        self.assertEqual(self.request(f"/api/policy/evaluations/{result['evaluation_id']}")[0], 401)

        with self.store.connect() as db:
            event_count_after = db.execute("SELECT COUNT(*) FROM world_events").fetchone()[0]
            projection_after = db.execute("SELECT version, state_json FROM world_state").fetchone()
            projection_after = (projection_after["version"], projection_after["state_json"])
        self.assertEqual(event_count_after, event_count_before)
        self.assertEqual(projection_after, projection_before)

    def test_simulation_replay_does_not_block_concurrent_gameplay_writes(self):
        status, session = self.request("/api/session", method="POST")
        self.assertEqual(status, 201)
        actor_id = session["player_id"]
        other_player_id = next(player_id for player_id in PLAYER_ENTITY_IDS if player_id != actor_id)
        replay_started = threading.Event()
        resume_replay = threading.Event()
        gameplay_finished = threading.Event()
        simulation_errors = []
        gameplay_errors = []
        simulations = []
        from atlas_server.simulation import run_simulation

        def paused_replay(events, proposal):
            replay_started.set()
            if not resume_replay.wait(timeout=3):
                raise TimeoutError("Test did not release the paused simulation.")
            return run_simulation(events, proposal)

        def run_simulation_thread():
            try:
                simulations.append(self.store.run_simulation(
                    {"rule": "beacon.lumen_reed_cost", "value": 3}, actor_id))
            except Exception as error:
                simulation_errors.append(error)

        def run_gameplay_thread():
            try:
                self.store.command({
                    "type": "move", "sequence": 1, "input": {"x": 0, "z": 0}, "run": False,
                }, other_player_id)
            except Exception as error:
                gameplay_errors.append(error)
            finally:
                gameplay_finished.set()

        simulation_thread = threading.Thread(target=run_simulation_thread)
        gameplay_thread = threading.Thread(target=run_gameplay_thread)
        with patch("atlas_server.store.simulate_recorded_events", side_effect=paused_replay):
            simulation_thread.start()
            try:
                self.assertTrue(replay_started.wait(timeout=2), "Simulation replay did not start.")
                gameplay_thread.start()
                met_latency_budget = gameplay_finished.wait(timeout=0.25)
            finally:
                resume_replay.set()
                simulation_thread.join(timeout=3)
                if gameplay_thread.ident is not None:
                    gameplay_thread.join(timeout=3)

        self.assertTrue(met_latency_budget, "Gameplay write exceeded the 250 ms latency budget.")
        self.assertFalse(simulation_thread.is_alive())
        self.assertFalse(gameplay_thread.is_alive())
        self.assertEqual(simulation_errors, [])
        self.assertEqual(gameplay_errors, [])
        self.assertEqual(len(simulations), 1)
        self.assertEqual(simulations[0]["as_of_sequence"], 0)
        self.assertEqual(self.store.read(other_player_id)[1][-1]["type"], "PlayerMoved")

    def test_simulation_rejects_history_over_the_declared_event_cap(self):
        status, session = self.request("/api/session", method="POST")
        self.assertEqual(status, 201)
        actor_id = session["player_id"]
        occurred_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        with self.store.connect() as db:
            for _ in range(3):
                db.execute(
                    """INSERT INTO world_events(
                           event_id, schema_version, occurred_at, event_type, actor_id,
                           source_kind, source_identifier, rationale, subject_id, object_id, payload_json
                       ) VALUES (?, 1, ?, 'ResourceGathered', ?, 'player_action', ?,
                                 'Observed test event', ?, NULL, ?)""",
                    (str(uuid4()), occurred_at, actor_id, str(uuid4()), actor_id,
                     json.dumps({"resource": "lumen_reed", "patch_id": str(uuid4()), "quantity": 1})),
                )

        with patch("atlas_server.store.MAX_SIMULATION_EVENT_HISTORY", 2):
            with self.assertRaisesRegex(ValueError, "exceeds the 2-event limit"):
                self.store.run_simulation({"rule": "beacon.lumen_reed_cost", "value": 3}, actor_id)

        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM simulation_runs").fetchone()[0], 0)

    def test_human_review_is_append_only_and_approval_still_does_not_deploy(self):
        status, session = self.request("/api/session", method="POST")
        self.assertEqual(status, 201)
        actor_id = session["player_id"]
        occurred_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        observed = []
        for patch_id in ("reed-west", "reed-north", "reed-east"):
            observed.append((str(uuid4()), "ResourceGathered", {
                "resource": "lumen_reed", "patch_id": patch_id, "quantity": 1}))
        observed.append((str(uuid4()), "BeaconAwakened", {
            "beacon_id": "beacon", "offering": {"lumen_reed": 3}, "result": "signal_received"}))
        with self.store.connect() as db:
            for event_id, event_type, payload in observed:
                db.execute(
                    """INSERT INTO world_events(
                           event_id, schema_version, occurred_at, event_type, actor_id,
                           source_kind, source_identifier, rationale, subject_id, object_id, payload_json
                       ) VALUES (?, 1, ?, ?, ?, 'player_action', ?, 'Observed test event', ?, ?, ?)""",
                    (event_id, occurred_at, event_type, actor_id, str(uuid4()), actor_id,
                     "b71e10e4-cb79-5c1e-9355-542c1d82512d" if event_type == "BeaconAwakened" else None,
                     json.dumps(payload, separators=(",", ":"))))
            before = db.execute("SELECT version, state_json FROM world_state WHERE singleton = 1").fetchone()
            projection_before = (before["version"], before["state_json"])
            event_count_before = db.execute("SELECT COUNT(*) FROM world_events").fetchone()[0]

        simulation = self.store.run_simulation({"rule": "beacon.lumen_reed_cost", "value": 3}, actor_id)
        self.assertEqual(simulation["baseline"]["recorded_activation_events"], 1)
        status, policy = self.request("/api/policy/evaluations", method="POST",
                                      body={"simulation_id": simulation["simulation_id"]},
                                      token=session["session_token"])
        self.assertEqual(status, 201)
        self.assertEqual(policy["status"], "eligible_for_human_review")
        status, decision = self.request("/api/decisions", method="POST", body={
            "simulation_id": simulation["simulation_id"], "evaluation_id": policy["evaluation_id"]},
            token=session["session_token"])
        self.assertEqual(status, 201)
        self.assertEqual(decision["status"], "awaiting_human_approval")

        status, review = self.request(f"/api/decisions/{decision['decision_id']}/review", method="POST",
                                      body={"action": "approve", "rationale": "Approved after reviewing the evidence."},
                                      token=session["session_token"])
        self.assertEqual(status, 201)
        self.assertEqual(review["status"], "approved_pending_deployment")
        self.assertFalse(review["world_change_applied"])
        loaded = self.request(f"/api/decisions/{decision['decision_id']}",
                              token=session["session_token"])[1]
        self.assertEqual(loaded["status"], "approved_pending_deployment")
        self.assertEqual(loaded["human_review"], review)
        duplicate_status, _ = self.request(f"/api/decisions/{decision['decision_id']}/review", method="POST",
                                           body={"action": "reject", "rationale": "Trying a second review."},
                                           token=session["session_token"])
        self.assertEqual(duplicate_status, 422)
        with self.store.connect() as db:
            after = db.execute("SELECT version, state_json FROM world_state WHERE singleton = 1").fetchone()
            self.assertEqual((after["version"], after["state_json"]), projection_before)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM world_events").fetchone()[0], event_count_before)

    def test_old_single_player_projection_migrates_without_losing_personal_or_shared_progress(self):
        path = Path(self.temp.name) / "legacy.sqlite3"
        legacy = initial_state()
        legacy["player"].update(x=6.25, y=8.5)
        legacy["inventory"]["lumen_reed"] = 2
        legacy["gathered"] = ["reed-west", "reed-north"]
        legacy["mara_met"] = True
        legacy["appearance"]["skin_tone"] = "#2468ac"
        import sqlite3
        with sqlite3.connect(path) as db:
            db.execute("CREATE TABLE world_state(singleton INTEGER PRIMARY KEY, version INTEGER NOT NULL, state_json TEXT NOT NULL)")
            db.execute("INSERT INTO world_state VALUES (1, 4, ?)", (json.dumps(legacy),))
        migrated = WorldStore(path, AtlasContracts(SPECS))
        first, _ = migrated.read(PLAYER_ENTITY_IDS[0])
        second, _ = migrated.read(PLAYER_ENTITY_IDS[1])
        self.assertEqual((first["player"]["x"], first["player"]["y"]), (6.25, 8.5))
        self.assertEqual(first["inventory"]["lumen_reed"], 2)
        self.assertTrue(first["mara_met"])
        self.assertEqual(first["gathered"], ["reed-west", "reed-north"])
        self.assertEqual(first["appearance"]["skin_tone"], "#2468ac")
        self.assertEqual(second["inventory"]["lumen_reed"], 0)
        self.assertEqual(second["player"]["x"], 4.2)
        with migrated.connect() as db:
            saved_state = json.loads(db.execute(
                "SELECT state_json FROM player_states WHERE player_id = ?", (PLAYER_ENTITY_IDS[0],)
            ).fetchone()["state_json"])
            profile = json.loads(db.execute(
                "SELECT appearance_json FROM player_profiles WHERE player_id = ?", (PLAYER_ENTITY_IDS[0],)
            ).fetchone()["appearance_json"])
        self.assertNotIn("appearance", saved_state)
        self.assertEqual(profile["skin_tone"], "#2468ac")


if __name__ == "__main__":
    unittest.main()
