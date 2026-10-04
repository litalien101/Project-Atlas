"""Compile a validated character profile and recipe into a frozen mesh-build plan.

This is the geometry-stage adapter between atlas-character-recipe/v1 and the
Blender blockout builder. It only plans supported parametric controls; it does
not claim to compile the full cross-category model-recipe contract.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/characters"))
from character_design_profile import load_profile  # noqa: E402

PROFILE_SCHEMA_PATH = ROOT / "specs/atlas-character-design-profile-v2.schema.json"
RECIPE_SCHEMA_PATH = ROOT / "specs/atlas-character-recipe-v1.schema.json"
PLAN_SCHEMA = "atlas-character-geometry-build-plan/v1"
BUILDER_PATH = ROOT / "tools/characters/generate_character_base.py"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def project_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def resolve_input_path(value: str) -> Path:
    path = Path(value).expanduser()
    return (path if path.is_absolute() else ROOT / path).resolve(strict=True)


def compile_plan(profile_path: Path, recipe_path: Path) -> dict[str, Any]:
    profile_path = profile_path.resolve(strict=True)
    recipe_path = recipe_path.resolve(strict=True)
    profile = load_profile(profile_path)
    source_profile = json.loads(profile_path.read_text(encoding="utf-8"))
    recipe = json.loads(recipe_path.read_text(encoding="utf-8"))

    profile_schema = json.loads(PROFILE_SCHEMA_PATH.read_text(encoding="utf-8"))
    recipe_schema = json.loads(RECIPE_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(profile_schema)
    Draft202012Validator.check_schema(recipe_schema)
    recipe_errors = sorted(Draft202012Validator(recipe_schema).iter_errors(recipe), key=lambda item: list(item.absolute_path))
    if recipe_errors:
        details = "; ".join(
            f"/{'/'.join(str(part) for part in error.absolute_path)}: {error.message}"
            for error in recipe_errors
        )
        raise ValueError(f"character recipe failed schema validation: {details}")
    if recipe["character_id"] != profile["character_id"]:
        raise ValueError("recipe character_id does not match the design profile")
    if recipe["profile_sha256"] != file_sha256(profile_path):
        raise ValueError("recipe profile_sha256 does not match the selected design profile")
    if recipe["builder"] != "atlas-parametric-body/v1":
        raise ValueError(f"unsupported character recipe builder: {recipe['builder']!r}")
    if recipe["pose"] != "t_pose_fingers_spread":
        raise ValueError("the geometry-stage builder currently requires t_pose_fingers_spread")

    build_profile = json.loads(json.dumps(profile))
    build_profile["body"] = recipe["body"]
    build_profile_errors = sorted(
        Draft202012Validator(profile_schema).iter_errors(build_profile),
        key=lambda item: list(item.absolute_path),
    )
    if build_profile_errors:
        details = "; ".join(
            f"/{'/'.join(str(part) for part in error.absolute_path)}: {error.message}"
            for error in build_profile_errors
        )
        raise ValueError(f"recipe body values are not supported by the profile contract: {details}")

    reference_geometry = None
    calibration = profile.get("reference_calibration")
    if calibration and calibration["use"] == "geometry_seed":
        review = calibration.get("geometry_seed_review", {})
        if review.get("status") != "approved":
            raise ValueError("geometry seed has no approved human review attestation")
        source_path = resolve_input_path(calibration["source_path"])
        record_path = resolve_input_path(calibration["record"])
        record = json.loads(record_path.read_text(encoding="utf-8"))
        source_hash = file_sha256(source_path)
        if source_hash != calibration["source_sha256"] or record.get("source_sha256") != source_hash:
            raise ValueError("geometry seed, profile, and calibration record source hashes do not agree")
        provenance = record.get("provenance", {})
        for field in ("title", "author", "license", "source"):
            if not isinstance(provenance.get(field), str) or not provenance[field].strip():
                raise ValueError(f"geometry seed calibration record is missing source provenance field {field!r}")
        if provenance["license"] != calibration["license"]:
            raise ValueError("geometry seed license in the profile does not match its calibration record")
        source_object = record.get("geometry", {}).get("selected_mesh_object")
        if not isinstance(source_object, str) or not source_object:
            raise ValueError("geometry calibration record must identify the selected source mesh object")
        reference_geometry = {
            "source": {"path": project_path(source_path), "sha256": source_hash},
            "calibration_record": {
                "path": project_path(record_path),
                "sha256": file_sha256(record_path),
                "snapshot": record,
            },
            "selected_mesh_object": source_object,
            "review": review,
        }

    plan: dict[str, Any] = {
        "schema": PLAN_SCHEMA,
        "plan_state": "candidate_only",
        "character_id": profile["character_id"],
        "quality_tier": "reference_seed_review" if reference_geometry else "blockout_only",
        "neutral_pose": recipe["pose"],
        "rigging": {
            "required_for_mesh_build": False,
            "armature_generated": False,
            "skin_weights_generated": False,
            "animation_generated": False,
        },
        "supported_recipe_scope": [
            "body proportion controls in character recipe body (procedural form or reviewed source-mesh warp)",
            "canonical T-pose selection",
            "profile archetype, feature toggles, palette, and intended-action metadata",
        ],
        "limitations": [
            "The procedural path creates low-detail blockout geometry; the reviewed-source path warps a selected mesh and remains a candidate, not a finished character.",
            "Anatomy relationship prose and material tags are retained as recipe evidence but are not geometry instructions yet.",
            "The model-recipe-v1 cross-category contract is not consumed by this character-stage plan.",
            "A human must review proportions, silhouette, hands, wrists, topology, and the complete T-pose.",
            *( ["Source mesh, calibration record, and human review are pinned by hashes; its rig and animations are not carried into the result."] if reference_geometry else [] ),
        ],
        "inputs": {
            "profile": {
                "path": project_path(profile_path),
                "sha256": file_sha256(profile_path),
                "snapshot": source_profile,
            },
            "character_recipe": {
                "path": project_path(recipe_path),
                "sha256": file_sha256(recipe_path),
                "snapshot": recipe,
            },
            "profile_schema": {
                "path": project_path(PROFILE_SCHEMA_PATH),
                "sha256": file_sha256(PROFILE_SCHEMA_PATH),
            },
            "recipe_schema": {
                "path": project_path(RECIPE_SCHEMA_PATH),
                "sha256": file_sha256(RECIPE_SCHEMA_PATH),
            },
            **({"reference_geometry": reference_geometry} if reference_geometry else {}),
        },
        "build_profile": build_profile,
        "builder": {
            "path": project_path(BUILDER_PATH),
            "sha256": file_sha256(BUILDER_PATH),
            "generator_version": "atlas-character-base/v28",
        },
        "compiler": {
            "path": project_path(Path(__file__)),
            "sha256": file_sha256(Path(__file__)),
        },
    }
    plan["plan_sha256"] = canonical_sha256(plan)
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", type=Path, help="Validated atlas-character-design-profile/v2 JSON")
    parser.add_argument("recipe", type=Path, help="Compiled atlas-character-recipe/v1 JSON")
    parser.add_argument("--output", type=Path, required=True, help="Frozen candidate build-plan JSON output")
    args = parser.parse_args()
    try:
        plan = compile_plan(args.profile, args.recipe)
        output_path = args.output if args.output.is_absolute() else ROOT / args.output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=output_path.parent,
            prefix=f".{output_path.name}.", suffix=".tmp", delete=False,
        ) as stream:
            temporary = Path(stream.name)
            json.dump(plan, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
        os.replace(temporary, output_path)
    except (OSError, json.JSONDecodeError, ValueError, KeyError) as error:
        print(f"BLOCKED: {error}", file=sys.stderr)
        return 1
    print(f"BUILD PLAN: {output_path} (candidate only; geometry is blockout quality)")
    print(f"Plan SHA-256: {plan['plan_sha256']}")
    print("Rigging, skin weights, and animation are not required or generated at this stage.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
