"""Loopback-only HTTP server for the local Reach game."""

from __future__ import annotations

import json
import hashlib
import os
import shutil
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

import yaml

from .contracts import AtlasContracts
from .reasoning import explain_event_provenance
from .store import SessionCapacityError, WorldStore, validate_action
from .world import public_state

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
ASSET_ROOT = Path(os.environ.get("ATLAS_ASSET_DIR") or WEB / "assets").expanduser().resolve()
DATA = Path(os.environ.get("ATLAS_DATA_DIR", ROOT / "data"))
SPECS = ROOT / "specs" / "atlas" / "specs"
MAX_BODY = 16384
ASSET_CONTENT_TYPES = {
    ".bin": "application/octet-stream",
    ".fbx": "application/octet-stream",
    ".glb": "model/gltf-binary",
    ".gltf": "model/gltf+json",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".ktx2": "image/ktx2",
    ".png": "image/png",
    ".webp": "image/webp",
}

class Handler(BaseHTTPRequestHandler):
    server_version = "AtlasLocal/0.1"
    store: WorldStore
    asset_root: Path = ASSET_ROOT

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        # GLTFLoader extracts textures embedded in GLB buffer views into blob URLs.
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; connect-src 'self' blob:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
        self.send_header("Cache-Control", getattr(self, "_cache_control", "no-store"))
        super().end_headers()

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/assets" or path.startswith("/assets/"):
            return self._serve_asset(path)
        if path == "/api/state":
            player_id = self.store.player_for_session(self.headers.get("X-Atlas-Session"))
            if player_id is None:
                return self._json(401, {"error": "A local traveler session is required."})
            state, events = self.store.read(player_id)
            response = public_state(state, events)
            response["last_processed_input"] = self.store.last_input_sequence_for(player_id)
            response["appearance"] = state.get("appearance")
            response["active_player"] = {"id": player_id, "name": next(p["name"] for p in state["players"] if p["is_self"])}
            return self._json(200, response)
        if path.startswith("/api/simulations/"):
            if self.store.player_for_session(self.headers.get("X-Atlas-Session")) is None:
                return self._json(401, {"error": "A local traveler session is required."})
            simulation_id = path.removeprefix("/api/simulations/")
            if not simulation_id or "/" in simulation_id or urlsplit(self.path).query:
                return self._json(400, {"error": "Simulation lookup requires one simulation UUID."})
            try:
                result = self.store.get_simulation(simulation_id)
            except ValueError as exc:
                return self._json(422, {"error": str(exc)})
            return self._json(200, result) if result else self._json(404, {"error": "Simulation was not found."})
        if path.startswith("/api/policy/evaluations/"):
            if self.store.player_for_session(self.headers.get("X-Atlas-Session")) is None:
                return self._json(401, {"error": "A local traveler session is required."})
            evaluation_id = path.removeprefix("/api/policy/evaluations/")
            if not evaluation_id or "/" in evaluation_id or urlsplit(self.path).query:
                return self._json(400, {"error": "Policy lookup requires one evaluation UUID."})
            try:
                result = self.store.get_policy_evaluation(evaluation_id)
            except ValueError as exc:
                return self._json(422, {"error": str(exc)})
            return self._json(200, result) if result else self._json(404, {"error": "Policy evaluation was not found."})
        if path.startswith("/api/decisions/"):
            if self.store.player_for_session(self.headers.get("X-Atlas-Session")) is None:
                return self._json(401, {"error": "A local traveler session is required."})
            decision_id = path.removeprefix("/api/decisions/")
            if not decision_id or "/" in decision_id or urlsplit(self.path).query:
                return self._json(400, {"error": "Decision lookup requires one decision UUID."})
            try:
                result = self.store.get_decision(decision_id)
            except ValueError as exc:
                return self._json(422, {"error": str(exc)})
            return self._json(200, result) if result else self._json(404, {"error": "Decision was not found."})
        if path in {"/api/knowledge", "/api/memory", "/api/analytics", "/api/reasoning"}:
            if self.store.player_for_session(self.headers.get("X-Atlas-Session")) is None:
                return self._json(401, {"error": "A local traveler session is required."})
            query = parse_qs(urlsplit(self.path).query, keep_blank_values=True)
            if any(len(values) != 1 for values in query.values()):
                return self._json(400, {"error": "Each query parameter may be supplied only once."})
            values = {key: items[0] for key, items in query.items()}
            try:
                if path == "/api/knowledge":
                    allowed = {"source", "target", "entity", "type", "limit"}
                    if values.keys() - allowed:
                        return self._json(400, {"error": "Unsupported knowledge query parameter."})
                    result = self.store.query_knowledge(
                        source_id=values.get("source") or None,
                        target_id=values.get("target") or None,
                        entity_id=values.get("entity") or None,
                        relation_type=values.get("type") or None,
                        limit=int(values.get("limit", "100")),
                    )
                elif path == "/api/memory":
                    allowed = {"entity", "type", "after", "limit"}
                    if values.keys() - allowed:
                        return self._json(400, {"error": "Unsupported memory query parameter."})
                    result = self.store.query_memory(
                        entity_id=values.get("entity") or None,
                        event_type=values.get("type") or None,
                        after_sequence=int(values.get("after", "0")),
                        limit=int(values.get("limit", "50")),
                    )
                elif path == "/api/analytics":
                    allowed = {"after", "limit"}
                    if values.keys() - allowed:
                        return self._json(400, {"error": "Unsupported analytics query parameter."})
                    result = self.store.query_analytics(
                        after_sequence=int(values.get("after", "0")),
                        limit=int(values.get("limit", "1000")),
                    )
                else:
                    allowed = {"event"}
                    if values.keys() - allowed:
                        return self._json(400, {"error": "Unsupported reasoning query parameter."})
                    if not values.get("event"):
                        return self._json(422, {"error": "Reasoning query requires an event UUID."})
                    record = self.store.explain_event(values["event"])
                    if record is None:
                        return self._json(404, {"error": "World event was not found."})
                    result = explain_event_provenance(record)
            except ValueError as exc:
                return self._json(422, {"error": str(exc)})
            return self._json(200, result)
        asset = {
            "/": "index.html",
            "/game.js": "game.js",
            "/styles.css": "styles.css",
            "/atlas-hud.css": "atlas-hud.css",
            "/atlas-panels.css": "atlas-panels.css",
        }.get(path)
        if asset is None:
            return self._json(404, {"error": "Not found"})
        content_type = "text/html; charset=utf-8" if asset.endswith(".html") else "text/javascript; charset=utf-8" if asset.endswith(".js") else "text/css; charset=utf-8"
        body = (WEB / asset).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_asset(self, request_path: str) -> None:
        try:
            relative_path = unquote(request_path.removeprefix("/assets/"), errors="strict")
            if not relative_path or "\\" in relative_path or "\x00" in relative_path:
                raise ValueError("invalid asset path")
            parts = relative_path.split("/")
            if any(part in {"", ".", ".."} for part in parts):
                raise ValueError("invalid asset path")
            content_type = ASSET_CONTENT_TYPES.get(Path(parts[-1]).suffix.lower())
            if content_type is None:
                raise FileNotFoundError

            root = Path(self.asset_root).resolve()
            asset_path = root.joinpath(*parts).resolve(strict=True)
            asset_path.relative_to(root)
            if not asset_path.is_file():
                raise FileNotFoundError
            if parts[0] == "clothing":
                manifest = yaml.safe_load((root / "manifest.yaml").read_text(encoding="utf-8"))
                if not isinstance(manifest, list):
                    raise FileNotFoundError
                entry = next((item for item in manifest if isinstance(item, dict)
                              and item.get("asset_kind") == "clothing"
                              and relative_path in item.get("files", [])), None)
                checksums = entry.get("checksum_sha256") if entry else None
                if (entry is None or entry.get("fit_review_status") != "approved"
                        or entry.get("redistribution_status") != "cleared"
                        or not entry.get("fit_reviewer")
                        or not isinstance(entry.get("fit_review_checklist"), dict)
                        or not entry["fit_review_checklist"]
                        or any(value is not True for value in entry["fit_review_checklist"].values())
                        or not isinstance(checksums, dict)):
                    raise FileNotFoundError
                digest = hashlib.sha256(asset_path.read_bytes()).hexdigest()
                if checksums.get(relative_path) != digest:
                    raise FileNotFoundError
            asset_file = asset_path.open("rb")
            asset_size = os.fstat(asset_file.fileno()).st_size
        except (FileNotFoundError, OSError, UnicodeError, ValueError):
            return self._json(404, {"error": "Not found"})

        with asset_file:
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(asset_size))
            self._cache_control = "public, max-age=3600"
            self.end_headers()
            shutil.copyfileobj(asset_file, self.wfile)

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if path == "/api/session":
            try:
                return self._json(201, self.store.create_session())
            except SessionCapacityError as exc:
                return self._json(409, {"error": str(exc)})
        if path == "/api/session/close":
            expected_host = f"127.0.0.1:{self.server.server_port}"
            allowed_origins = {f"http://127.0.0.1:{self.server.server_port}",
                               f"http://localhost:{self.server.server_port}"}
            if self.headers.get("Host", "").lower() not in {expected_host, f"localhost:{self.server.server_port}"}:
                return self._json(403, {"error": "Invalid host"})
            origin = self.headers.get("Origin")
            if origin and origin not in allowed_origins:
                return self._json(403, {"error": "Cross-origin session close is not allowed"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 1 or length > 1024:
                    return self._json(400, {"error": "Session close requires a valid session token."})
                payload = json.loads(self.rfile.read(length))
                token = payload.get("session_token") if isinstance(payload, dict) else None
                if not isinstance(token, str):
                    return self._json(400, {"error": "Session close requires a valid session token."})
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
                return self._json(400, {"error": "Session close request is malformed."})
            self.store.close_session(token)
            return self._json(200, {"closed": True})
        if path == "/api/appearance":
            expected_host = f"127.0.0.1:{self.server.server_port}"
            allowed_hosts = {expected_host, f"localhost:{self.server.server_port}"}
            allowed_origins = {f"http://127.0.0.1:{self.server.server_port}",
                               f"http://localhost:{self.server.server_port}"}
            if self.headers.get("Host", "").lower() not in allowed_hosts:
                return self._json(403, {"error": "Invalid host"})
            origin = self.headers.get("Origin")
            if origin and origin not in allowed_origins:
                return self._json(403, {"error": "Cross-origin appearance updates are not allowed"})
            player_id = self.store.player_for_session(self.headers.get("X-Atlas-Session"))
            if player_id is None:
                return self._json(401, {"error": "A local traveler session is required."})
            if urlsplit(self.path).query:
                return self._json(400, {"error": "Appearance updates do not accept query parameters."})
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return self._json(400, {"error": "Invalid content length"})
            if length < 1 or length > 4096:
                return self._json(413, {"error": "Appearance request is too large or empty"})
            if self.headers.get_content_type() != "application/json":
                return self._json(415, {"error": "Expected application/json"})
            try:
                content = json.loads(self.rfile.read(length))
                if not isinstance(content, dict) or set(content) != {"appearance"}:
                    raise ValueError("Appearance update must contain exactly one appearance profile.")
                profile = self.store.save_appearance(player_id, content["appearance"])
            except (UnicodeDecodeError, json.JSONDecodeError):
                return self._json(400, {"error": "Malformed JSON"})
            except ValueError as exc:
                return self._json(422, {"error": str(exc)})
            except Exception:
                self.log_error("request failed while saving a character appearance")
                return self._json(500, {"error": "The character appearance could not be saved."})
            return self._json(200, {"appearance": profile})
        if path in {"/api/entities", "/api/relationships", "/api/simulations",
                    "/api/policy/evaluations", "/api/decisions"} or path.startswith("/api/decisions/"):
            expected_host = f"127.0.0.1:{self.server.server_port}"
            if self.headers.get("Host", "").lower() not in {expected_host, f"localhost:{self.server.server_port}"}:
                return self._json(403, {"error": "Invalid host"})
            origin = self.headers.get("Origin")
            if origin and origin not in {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}:
                return self._json(403, {"error": "Cross-origin authoring is not allowed"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return self._json(400, {"error": "Invalid content length"})
            if length < 1 or length > MAX_BODY:
                return self._json(413, {"error": "Authoring request is too large or empty"})
            if self.headers.get_content_type() != "application/json":
                return self._json(415, {"error": "Expected application/json"})
            try:
                content = json.loads(self.rfile.read(length))
                if path.startswith("/api/decisions/") and path.endswith("/review"):
                    player_id = self.store.player_for_session(self.headers.get("X-Atlas-Session"))
                    if player_id is None:
                        return self._json(401, {"error": "A local human reviewer session is required."})
                    if urlsplit(self.path).query:
                        return self._json(400, {"error": "Decision review does not accept query parameters."})
                    decision_id = path.removeprefix("/api/decisions/").removesuffix("/review").rstrip("/")
                    if not isinstance(content, dict) or set(content) != {"action", "rationale"}:
                        raise ValueError("Decision review requires exactly an action and rationale.")
                    result = self.store.review_decision(decision_id, content["action"],
                                                        content["rationale"], player_id)
                    return self._json(201, result)
                if path == "/api/decisions":
                    player_id = self.store.player_for_session(self.headers.get("X-Atlas-Session"))
                    if player_id is None:
                        return self._json(401, {"error": "A local traveler session is required."})
                    if not isinstance(content, dict) or set(content) != {"simulation_id", "evaluation_id"}:
                        raise ValueError("Decision creation requires a simulation_id and matching evaluation_id.")
                    result = self.store.create_decision(content["simulation_id"], content["evaluation_id"], player_id)
                    return self._json(201, result)
                if path == "/api/policy/evaluations":
                    player_id = self.store.player_for_session(self.headers.get("X-Atlas-Session"))
                    if player_id is None:
                        return self._json(401, {"error": "A local traveler session is required."})
                    if not isinstance(content, dict) or set(content) != {"simulation_id"}:
                        raise ValueError("Policy evaluation requires exactly one persisted simulation_id.")
                    result = self.store.evaluate_policy(content["simulation_id"], player_id)
                    return self._json(201, result)
                if path == "/api/simulations":
                    player_id = self.store.player_for_session(self.headers.get("X-Atlas-Session"))
                    if player_id is None:
                        return self._json(401, {"error": "A local traveler session is required."})
                    result = self.store.run_simulation(content.get("proposed_change") if isinstance(content, dict) else None,
                                                       player_id)
                    return self._json(201, result)
                if not isinstance(content, dict) or not isinstance(content.get("source"), dict):
                    raise ValueError("Authoring request must include a source reference.")
                source = content["source"]
                if path == "/api/entities":
                    event = self.store.create_entity(
                        content.get("entity"), source_kind=source.get("kind"),
                        source_identifier=source.get("identifier"), rationale=content.get("rationale"),
                    )
                else:
                    event = self.store.create_relationship(
                        content.get("type"), content.get("source_id"), content.get("target_id"),
                        source_kind=source.get("kind"), source_identifier=source.get("identifier"),
                        rationale=content.get("rationale"),
                    )
            except (UnicodeDecodeError, json.JSONDecodeError):
                return self._json(400, {"error": "Malformed JSON"})
            except ValueError as exc:
                return self._json(422, {"error": str(exc)})
            except Exception:
                self.log_error("request failed while creating an Atlas world entity or relationship")
                return self._json(500, {"error": "The Atlas world change could not be saved."})
            return self._json(201, event)
        if path != "/api/action":
            return self._json(404, {"error": "Not found"})
        expected_host = f"127.0.0.1:{self.server.server_port}"
        if self.headers.get("Host", "").lower() not in {expected_host, f"localhost:{self.server.server_port}"}:
            return self._json(403, {"error": "Invalid host"})
        origin = self.headers.get("Origin")
        if origin and origin not in {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}:
            return self._json(403, {"error": "Cross-origin actions are not allowed"})
        player_id = self.store.player_for_session(self.headers.get("X-Atlas-Session"))
        if player_id is None:
            return self._json(401, {"error": "A local traveler session is required."})
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self._json(400, {"error": "Invalid content length"})
        if length < 1 or length > MAX_BODY:
            return self._json(413, {"error": "Action request is too large or empty"})
        if self.headers.get_content_type() != "application/json":
            return self._json(415, {"error": "Expected application/json"})
        try:
            action = json.loads(self.rfile.read(length))
            action = validate_action(action)
            event = self.store.command(action, player_id)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self._json(400, {"error": "Malformed JSON"})
        except ValueError as exc:
            return self._json(422, {"error": str(exc)})
        except Exception:
            self.log_error("request failed while applying an action")
            return self._json(500, {"error": "The action could not be saved."})
        return self._json(200, event)

    def _json(self, status: int, value: object) -> None:
        body = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"[{self.log_date_time_string()}] {self.address_string()} {fmt % args}")

def main() -> None:
    host = os.environ.get("ATLAS_HOST", "127.0.0.1")
    if host not in {"127.0.0.1", "localhost"}:
        raise SystemExit("This prototype is loopback-only. Do not expose it to a network.")
    port = int(os.environ.get("ATLAS_PORT", "8765"))
    contracts = AtlasContracts(SPECS)
    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    Handler.store = WorldStore(DATA / "world.sqlite3", contracts)
    print(f"The Reach is running at http://127.0.0.1:{server.server_port} (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down The Reach.")
    finally:
        server.server_close()
