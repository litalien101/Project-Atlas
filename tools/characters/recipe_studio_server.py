"""Serve the local deterministic character recipe workbench on loopback."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[2]
UI_ROOT = Path(__file__).resolve().parent / "recipe_studio"
DRAFT_ROOT = ROOT / "data/recipe_studio/drafts"
CANDIDATE_ROOT = ROOT / "art/characters/pending_models/recipe_studio"
REVIEW_ROOT = ROOT / "art/characters/pending_models/troll_sample_1"
ANNOTATION_ROOT = ROOT / "data/model_reviews/troll_sample_1"
MAX_BODY = 256_000
sys.path.insert(0, str(Path(__file__).resolve().parent))
from character_design_profile import validate_profile  # noqa: E402
from compile_character_geometry_plan import compile_plan  # noqa: E402
from compile_character_recipe import DEFAULT_GRAMMAR, compile_recipe, digest  # noqa: E402
from deterministic_recipe_compiler import compile_text  # noqa: E402


class Handler(BaseHTTPRequestHandler):
    server_version = "AtlasRecipeStudio/0.1"

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self'; connect-src 'self'; img-src 'self' data: blob:; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/api/health":
            return self._json(200, {
                "service": "atlas-deterministic-character-recipe-studio/v1",
                "ai_service": False,
                "blender_available": bool(shutil.which(os.environ.get("BLENDER_BIN", "blender"))),
            })
        if path == "/api/candidates":
            return self._json(200, {"candidates": self._list_candidates()})
        if path == "/api/model-review/models":
            return self._json(200, {"models": self._review_models()})
        if path == "/api/model-review/annotations":
            query = parse_qs(urlsplit(self.path).query)
            model_id = query.get("model_id", [None])[0]
            if model_id not in self._review_model_map():
                return self._json(400, {"error": "Unknown review model."})
            return self._read_annotations(model_id)
        if path == "/api/model-review/model":
            query = parse_qs(urlsplit(self.path).query)
            model_id = query.get("model_id", [None])[0]
            model = self._review_model_map().get(model_id)
            if model is None or model.is_symlink() or not model.is_file():
                return self._json(404, {"error": "Review model was not found."})
            return self._send_file(model, "model/gltf-binary")
        if path == "/api/model-review/blend":
            query = parse_qs(urlsplit(self.path).query)
            model_id = query.get("model_id", [None])[0]
            glb = self._review_model_map().get(model_id)
            blend = glb.with_suffix(".blend") if glb else None
            if blend is None or blend.is_symlink() or not blend.is_file():
                return self._json(404, {"error": "Blender project was not found."})
            return self._send_file(blend, "application/octet-stream", download_name=blend.name)
        if path == "/api/candidate/preview":
            query = parse_qs(urlsplit(self.path).query, keep_blank_values=True)
            if set(query) != {"draft_id", "build_id"} or any(len(values) != 1 for values in query.values()):
                return self._json(400, {"error": "Preview requires one draft ID and one build ID."})
            draft_id, build_id = query["draft_id"][0], query["build_id"][0]
            if not re.fullmatch(r"[0-9a-f-]{36}", draft_id) or not re.fullmatch(r"[0-9a-f-]{36}", build_id):
                return self._json(400, {"error": "Invalid candidate identifier."})
            preview = (
                ROOT / "art/characters/pending_models/recipe_studio" /
                draft_id / build_id / "stone_troll/character_base_preview.glb"
            ).resolve()
            allowed_root = (ROOT / "art/characters/pending_models/recipe_studio").resolve()
            if allowed_root not in preview.parents:
                return self._json(403, {"error": "Preview path is outside the candidate directory."})
            if not preview.is_file():
                return self._json(404, {"error": "No Stone Troll preview has been built yet."})
            content = preview.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "model/gltf-binary")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return
        if path.startswith("/vendor/"):
            relative = path.removeprefix("/vendor/")
            vendor_root = ROOT / "node_modules/three"
            vendor_path = (vendor_root / relative).resolve()
            if vendor_root.resolve() not in vendor_path.parents or not vendor_path.is_file():
                return self._json(404, {"error": "Preview renderer dependency is unavailable."})
            content = vendor_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/javascript; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return
        names = {
            "/": "review.html", "/review": "review.html", "/review/": "review.html",
            "/builder": "index.html", "/builder/": "index.html",
            "/studio.css": "studio.css", "/studio.js": "studio.js",
            "/review.css": "review.css", "/review.js": "review.js",
        }
        name = names.get(path)
        if name is None:
            return self._json(404, {"error": "Page not found."})
        target = UI_ROOT / name
        try:
            content = target.read_bytes()
        except OSError:
            return self._json(500, {"error": "The recipe studio UI file is unavailable."})
        content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type + ("; charset=utf-8" if content_type.startswith("text/") or "javascript" in content_type else ""))
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self) -> None:
        origin = self.headers.get("Origin")
        allowed_origins = {
            f"http://127.0.0.1:{self.server.server_port}",
            f"http://localhost:{self.server.server_port}",
        }
        if origin and origin not in allowed_origins:
            return self._json(403, {"error": "Cross-origin recipe requests are not allowed."})
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self._json(400, {"error": "Invalid content length."})
        if length < 1 or length > MAX_BODY:
            return self._json(413, {"error": "Request is empty or too large."})
        if self.headers.get_content_type() != "application/json":
            return self._json(415, {"error": "Expected application/json."})
        try:
            content = json.loads(self.rfile.read(length))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self._json(400, {"error": "Malformed JSON."})
        if not isinstance(content, dict):
            return self._json(400, {"error": "Request body must be a JSON object."})

        path = urlsplit(self.path).path
        try:
            if path == "/api/compile":
                if set(content) != {"prompt"} or not isinstance(content["prompt"], str):
                    return self._json(422, {"error": "Provide only a prompt string."})
                return self._json(200, compile_text(content["prompt"]))
            if path == "/api/plan":
                return self._compile_plan(content)
            if path == "/api/build":
                return self._build_candidate(content)
            if path == "/api/candidate/review":
                return self._review_candidate(content)
            if path == "/api/model-review/annotations":
                return self._write_annotations(content)
            return self._json(404, {"error": "API endpoint not found."})
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
            return self._json(422, {"error": str(error)})
        except subprocess.TimeoutExpired:
            return self._json(504, {"error": "Blender did not finish within five minutes. Check the local Blender process and retry."})
        except Exception:
            self.log_error("recipe studio request failed")
            return self._json(500, {"error": "The local recipe operation failed. See the server log."})

    def _compile_plan(self, content: dict) -> None:
        if not isinstance(content.get("profile"), dict) or not isinstance(content.get("prompt"), str):
            return self._json(422, {"error": "Provide a profile object and its original prompt."})
        profile = validate_profile(content["profile"])
        if profile["character_id"] != "stone_troll":
            return self._json(422, {"error": "This first workbench only supports the Stone Troll profile."})
        draft_id = str(uuid.uuid4())
        draft_dir = DRAFT_ROOT / draft_id
        draft_dir.mkdir(parents=True, exist_ok=False)
        profile_path = draft_dir / "design_profile.json"
        recipe_path = draft_dir / "character_recipe.json"
        plan_path = draft_dir / "geometry_build_plan.json"
        profile_path.write_text(json.dumps(profile, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        grammar = json.loads(DEFAULT_GRAMMAR.read_text(encoding="utf-8"))
        recipe = compile_recipe(
            profile,
            grammar,
            digest(profile_path),
            digest(DEFAULT_GRAMMAR),
            include_draft_rules=True,
        )
        recipe_path.write_text(json.dumps(recipe, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        plan = compile_plan(profile_path, recipe_path)
        plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self._json(200, {
            "draft_id": draft_id,
            "profile": profile,
            "recipe": recipe,
            "plan": {
                "schema": plan["schema"],
                "plan_sha256": plan["plan_sha256"],
                "path": str(plan_path.relative_to(ROOT)),
                "quality_tier": plan["quality_tier"],
                "neutral_pose": plan["neutral_pose"],
            },
            "saved_under": str(draft_dir.relative_to(ROOT)),
        })

    def _build_candidate(self, content: dict) -> None:
        draft_id = content.get("draft_id")
        if not isinstance(draft_id, str) or not re.fullmatch(r"[0-9a-f-]{36}", draft_id):
            return self._json(422, {"error": "A valid recipe draft ID is required."})
        draft_dir = (DRAFT_ROOT / draft_id).resolve()
        if draft_dir.parent != DRAFT_ROOT.resolve() or not draft_dir.is_dir():
            return self._json(404, {"error": "Recipe draft was not found."})
        plan_path = draft_dir / "geometry_build_plan.json"
        if not plan_path.is_file():
            return self._json(404, {"error": "The draft has no compiled geometry plan."})
        blender = shutil.which(os.environ.get("BLENDER_BIN", "blender"))
        if not blender:
            return self._json(503, {"error": "Blender was not found. Install Blender 4.x or newer or set BLENDER_BIN."})
        generator = ROOT / "tools/characters/generate_character_base.py"
        build_id = str(uuid.uuid4())
        output_root = CANDIDATE_ROOT / draft_id / build_id
        result = subprocess.run(
            [
                blender, "--background", "--python", str(generator), "--",
                "--build-plan", str(plan_path), "--allow-blockout",
                "--output-root", str(output_root),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        if result.returncode != 0:
            details = (result.stderr or result.stdout).strip()[-4000:]
            return self._json(422, {
                "error": "Blender rejected or failed to build the blockout candidate.",
                "details": details,
            })
        candidate_dir = output_root / "stone_troll"
        record_path = candidate_dir / "character.json"
        record = json.loads(record_path.read_text(encoding="utf-8"))
        self._json(200, {
            "draft_id": draft_id,
            "build_id": build_id,
            "candidate_status": "review_required",
            "quality_tier": record["generation_quality"]["tier"],
            "production_ready": record["generation_quality"]["production_ready"],
            "rigging": record["rigging"],
            "candidate_directory": str(candidate_dir.relative_to(ROOT)),
            "preview_url": f"/api/candidate/preview?draft_id={draft_id}&build_id={build_id}",
            "preview_path": str((candidate_dir / record["files"]["preview_glb"]).relative_to(ROOT)),
            "record_path": str(record_path.relative_to(ROOT)),
            "vertex_count": record["mesh"]["vertex_count"],
            "polygon_count": record["mesh"]["polygon_count"],
            "stdout": result.stdout.strip()[-2500:],
        })

    @staticmethod
    def _valid_id(value: object) -> bool:
        if not isinstance(value, str):
            return False
        try:
            return str(uuid.UUID(value)) == value
        except ValueError:
            return False

    def _candidate_directory(self, draft_id: object, build_id: object) -> Path | None:
        if not self._valid_id(draft_id) or not self._valid_id(build_id):
            return None
        if CANDIDATE_ROOT.is_symlink():
            return None
        draft_path = CANDIDATE_ROOT / draft_id
        candidate_path = draft_path / build_id
        if draft_path.is_symlink() or candidate_path.is_symlink():
            return None
        root = CANDIDATE_ROOT.resolve()
        draft = draft_path.resolve()
        candidate = candidate_path.resolve()
        if draft.parent != root or candidate.parent != draft or not candidate.is_dir():
            return None
        # The expected record makes this a Recipe Studio build, not an arbitrary
        # directory that happens to be beneath the candidate root.
        if not (candidate / "stone_troll" / "character.json").is_file():
            return None
        return candidate

    def _list_candidates(self) -> list[dict]:
        candidates: list[dict] = []
        if not CANDIDATE_ROOT.is_dir():
            return candidates
        for draft in CANDIDATE_ROOT.iterdir():
            if draft.is_symlink() or not draft.is_dir() or not self._valid_id(draft.name):
                continue
            for build in draft.iterdir():
                if build.is_symlink() or not build.is_dir() or not self._valid_id(build.name):
                    continue
                candidate_dir = self._candidate_directory(draft.name, build.name)
                if candidate_dir is None:
                    continue
                model_dir = candidate_dir / "stone_troll"
                try:
                    record = json.loads((model_dir / "character.json").read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                review_path = candidate_dir / "review.json"
                try:
                    review = json.loads(review_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    review = {"status": "review_required"}
                preview = model_dir / record.get("files", {}).get("preview_glb", "character_base_preview.glb")
                try:
                    built_at = datetime.fromtimestamp(model_dir.stat().st_mtime, timezone.utc).isoformat()
                except OSError:
                    built_at = None
                candidates.append({
                    "draft_id": draft.name,
                    "build_id": build.name,
                    "character_id": record.get("character_id", "stone_troll"),
                    "quality_tier": record.get("generation_quality", {}).get("tier", "unknown"),
                    "production_ready": bool(record.get("generation_quality", {}).get("production_ready", False)),
                    "vertex_count": record.get("mesh", {}).get("vertex_count"),
                    "polygon_count": record.get("mesh", {}).get("polygon_count"),
                    "review_status": review.get("status", "review_required"),
                    "reviewed_at": review.get("reviewed_at"),
                    "built_at": built_at,
                    "has_preview": preview.is_file(),
                    "preview_url": f"/api/candidate/preview?draft_id={draft.name}&build_id={build.name}",
                    "candidate_directory": str(candidate_dir.relative_to(ROOT)),
                })
        candidates.sort(key=lambda item: item["built_at"] or "", reverse=True)
        return candidates

    def _review_candidate(self, content: dict) -> None:
        if set(content) != {"draft_id", "build_id", "action"}:
            return self._json(422, {"error": "Provide draft_id, build_id, and action."})
        candidate = self._candidate_directory(content["draft_id"], content["build_id"])
        if candidate is None:
            return self._json(404, {"error": "Generated candidate was not found."})
        action = content["action"]
        if action == "keep":
            review = {
                "schema": "atlas-character-candidate-review/v1",
                "status": "kept_for_reference",
                "draft_id": content["draft_id"],
                "build_id": content["build_id"],
                "reviewed_at": datetime.now(timezone.utc).isoformat(),
            }
            review_path = candidate / "review.json"
            temporary_path = candidate / f".review.{uuid.uuid4().hex}.tmp"
            with temporary_path.open("x", encoding="utf-8") as stream:
                stream.write(json.dumps(review, indent=2) + "\n")
            temporary_path.replace(review_path)
            return self._json(200, {"status": review["status"], "reviewed_at": review["reviewed_at"]})
        if action == "delete":
            # Resolve and recheck immediately before removal. This endpoint only
            # accepts complete Recipe Studio builds and cannot address source,
            # other pending-model folders, or runtime assets.
            candidate = self._candidate_directory(content["draft_id"], content["build_id"])
            if candidate is None or candidate.parent.parent != CANDIDATE_ROOT.resolve():
                return self._json(404, {"error": "Generated candidate could not be safely located."})
            shutil.rmtree(candidate)
            return self._json(200, {"status": "deleted"})
        return self._json(422, {"error": "Action must be 'keep' or 'delete'."})

    @staticmethod
    def _review_model_map() -> dict[str, Path]:
        # Deliberately allow-list review candidates; this endpoint cannot read
        # arbitrary workspace files or source-model directories.
        return {
            "r002": REVIEW_ROOT / "voxel-remesh-r002/geometry_candidate.glb",
            "r002-adaptive": REVIEW_ROOT / "voxel-remesh-r002-adaptive/geometry_candidate.glb",
            "r003": REVIEW_ROOT / "voxel-remesh-r003/geometry_candidate.glb",
            "r004-fine": REVIEW_ROOT / "voxel-remesh-r004-fine/geometry_candidate.glb",
        }

    def _review_models(self) -> list[dict]:
        models = []
        for model_id, path in self._review_model_map().items():
            if path.is_symlink() or not path.is_file():
                continue
            models.append({
                "id": model_id,
                "label": f"Troll Sample 1 · {model_id}",
                "size_bytes": path.stat().st_size,
                "url": f"/api/model-review/model?model_id={model_id}",
                "blend_path": str(path.with_suffix(".blend").relative_to(ROOT)),
            })
        return models

    def _read_annotations(self, model_id: str) -> None:
        path = ANNOTATION_ROOT / f"{model_id}.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            data = {"schema": "atlas-model-review/v1", "model_id": model_id, "markers": []}
        except (OSError, json.JSONDecodeError):
            return self._json(500, {"error": "Saved annotations could not be read."})
        return self._json(200, data)

    def _write_annotations(self, content: dict) -> None:
        if set(content) != {"model_id", "markers"}:
            return self._json(422, {"error": "Provide model_id and markers."})
        model_id, markers = content["model_id"], content["markers"]
        if model_id not in self._review_model_map() or not isinstance(markers, list) or len(markers) > 200:
            return self._json(422, {"error": "Unknown model or invalid marker list."})
        clean = []
        for marker in markers:
            if not isinstance(marker, dict) or set(marker) != {"id", "position", "note", "created_at"}:
                return self._json(422, {"error": "Each marker needs id, position, note, and created_at."})
            position = marker["position"]
            if (not isinstance(marker["id"], str) or len(marker["id"]) > 80
                or not isinstance(position, list) or len(position) != 3
                or any(not isinstance(v, (int, float)) or not (-10 <= v <= 10) for v in position)
                or not isinstance(marker["note"], str) or not marker["note"].strip()
                or len(marker["note"]) > 1000 or not isinstance(marker["created_at"], str)):
                return self._json(422, {"error": "A marker contains invalid coordinates or note text."})
            clean.append({"id": marker["id"], "position": position, "note": marker["note"].strip(), "created_at": marker["created_at"]})
        ANNOTATION_ROOT.mkdir(parents=True, exist_ok=True)
        target = ANNOTATION_ROOT / f"{model_id}.json"
        temporary = ANNOTATION_ROOT / f".{model_id}.{uuid.uuid4().hex}.tmp"
        document = {"schema": "atlas-model-review/v1", "model_id": model_id, "updated_at": datetime.now(timezone.utc).isoformat(), "markers": clean}
        with temporary.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(document, indent=2, ensure_ascii=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(target)
        return self._json(200, document)

    def _send_file(self, path: Path, content_type: str, download_name: str | None = None) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(path.stat().st_size))
        if download_name:
            self.send_header("Content-Disposition", f'attachment; filename="{download_name}"')
        self.end_headers()
        with path.open("rb") as stream:
            shutil.copyfileobj(stream, self.wfile)

    def _json(self, status: int, value: object) -> None:
        body = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        print(f"[recipe-studio] {self.address_string()} {format % args}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("--port must be between 1024 and 65535")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Atlas Recipe Studio: http://127.0.0.1:{args.port}")
    print("Local deterministic compiler only; no AI or remote service is used.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Atlas Recipe Studio.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
