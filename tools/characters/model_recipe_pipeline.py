"""Validation and deterministic build-plan compilation for Atlas model recipes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "specs/atlas-model-recipe-v1.schema.json"
PLAN_SCHEMA = "atlas-build-plan/v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_contract() -> tuple[dict[str, Any], Draft202012Validator]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return schema, Draft202012Validator(schema, format_checker=FormatChecker())


def _unique_ids(items: Any, key: str, pointer: str, errors: list[str]) -> set[Any]:
    if not isinstance(items, list):
        return set()
    seen: set[Any] = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        value = item.get(key)
        if not isinstance(value, str):
            continue
        if value in seen:
            errors.append(f"{pointer}/{index}/{key}: duplicate ID {value!r}")
        seen.add(value)
    return seen


def _semantic_errors(recipe: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    _unique_ids(recipe.get("parameters"), "parameter_id", "/parameters", errors)
    _unique_ids(
        recipe.get("dimensions", {}).get("measurements"),
        "measurement_id", "/dimensions/measurements", errors,
    )
    landmarks = _unique_ids(
        recipe.get("dimensions", {}).get("landmarks"),
        "landmark_id", "/dimensions/landmarks", errors,
    )
    regions = _unique_ids(
        recipe.get("geometry", {}).get("surface_regions"),
        "region_id", "/geometry/surface_regions", errors,
    )
    materials = _unique_ids(recipe.get("materials"), "material_id", "/materials", errors)
    components = _unique_ids(recipe.get("components"), "component_id", "/components", errors)
    _unique_ids(recipe.get("variants"), "variant_id", "/variants", errors)
    _unique_ids(recipe.get("lods"), "level", "/lods", errors)
    _unique_ids(recipe.get("outputs"), "role", "/outputs", errors)

    frame = recipe.get("dimensions", {}).get("coordinate_frame", {})
    up = str(frame.get("up_axis", ""))[-1:]
    forward = str(frame.get("forward_axis", ""))[-1:]
    if up and forward and up == forward:
        errors.append("/dimensions/coordinate_frame: up_axis and forward_axis must be perpendicular")

    for index, parameter in enumerate(recipe.get("parameters", [])):
        if not isinstance(parameter, dict):
            continue
        low, high = parameter.get("minimum"), parameter.get("maximum")
        value = parameter.get("value")
        pointer = f"/parameters/{index}"
        if low is not None and high is not None and low > high:
            errors.append(f"{pointer}: minimum exceeds maximum")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if low is not None and value < low:
                errors.append(f"{pointer}/value: value is below minimum")
            if high is not None and value > high:
                errors.append(f"{pointer}/value: value exceeds maximum")

    for index, region in enumerate(recipe.get("geometry", {}).get("surface_regions", [])):
        if not isinstance(region, dict):
            continue
        for related in region.get("connected_to", []):
            if related not in regions:
                errors.append(f"/geometry/surface_regions/{index}/connected_to: unknown region {related!r}")
        for landmark in region.get("landmarks", []):
            if landmark not in landmarks:
                errors.append(f"/geometry/surface_regions/{index}/landmarks: unknown landmark {landmark!r}")

    for index, item in enumerate(recipe.get("geometry", {}).get("topology", {}).get("connected_region_groups", [])):
        for region_id in item:
            if region_id not in regions:
                errors.append(f"/geometry/topology/connected_region_groups/{index}: unknown region {region_id!r}")

    for index, assignment in enumerate(recipe.get("material_assignments", [])):
        if not isinstance(assignment, dict):
            continue
        material_id = assignment.get("material_id")
        if material_id not in materials:
            errors.append(f"/material_assignments/{index}/material_id: unknown material {material_id!r}")
        target_id = assignment.get("target_id")
        target_kind = assignment.get("target_kind")
        known = regions if target_kind == "surface_region" else components if target_kind == "component" else regions | components
        if target_id not in known:
            errors.append(f"/material_assignments/{index}/target_id: unknown target {target_id!r}")

    for index, component in enumerate(recipe.get("components", [])):
        if not isinstance(component, dict):
            continue
        for relationship in component.get("relationships", []):
            target_id = relationship.get("target_id") if isinstance(relationship, dict) else None
            if target_id not in components:
                errors.append(f"/components/{index}/relationships: unknown component {target_id!r}")

    for index, collider in enumerate(recipe.get("collision", {}).get("shapes", [])):
        region_id = collider.get("region_id") if isinstance(collider, dict) else None
        if region_id is not None and region_id not in regions:
            errors.append(f"/collision/shapes/{index}/region_id: unknown region {region_id!r}")

    for index, assignment in enumerate(recipe.get("material_assignments", [])):
        target_kind = assignment.get("target_kind") if isinstance(assignment, dict) else None
        if target_kind not in {None, "surface_region", "component"}:
            errors.append(f"/material_assignments/{index}/target_kind: unsupported target kind")

    return errors


def _file_refs(value: Any, pointer: str = "") -> list[tuple[str, dict[str, Any]]]:
    refs: list[tuple[str, dict[str, Any]]] = []
    if isinstance(value, dict):
        if (isinstance(value.get("path"), str) or isinstance(value.get("file"), str)) and isinstance(
            value.get("sha256"), str
        ):
            refs.append((pointer, value))
        for key, child in value.items():
            refs.extend(_file_refs(child, f"{pointer}/{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            refs.extend(_file_refs(child, f"{pointer}/{index}"))
    return refs


def _ref_path(reference: dict[str, Any]) -> str:
    return reference.get("path", reference.get("file", ""))


def validate_recipe(recipe: Any, recipe_path: Path, check_files: bool = True) -> list[str]:
    _, validator = load_contract()
    errors = [
        f"/{'/'.join(str(part) for part in issue.absolute_path)}: {issue.message}"
        for issue in validator.iter_errors(recipe)
    ]
    if errors or not isinstance(recipe, dict):
        return errors

    errors.extend(_semantic_errors(recipe))
    source_rights = recipe.get("provenance", {}).get("sources", [])
    restricted_sources = [
        source.get("reference", "<unknown>")
        for source in source_rights
        if isinstance(source, dict) and source.get("rights_status") == "restricted"
    ]
    if restricted_sources:
        errors.append("/provenance/sources: restricted sources cannot enter a build plan: "
                      + ", ".join(restricted_sources))

    failed_checks = [
        check.get("check_id", "<unnamed>")
        for check in recipe.get("validation", {}).get("checks", [])
        if isinstance(check, dict) and check.get("status") == "fail"
    ]
    if failed_checks:
        errors.append("/validation/checks: failed checks block build planning: " + ", ".join(failed_checks))
    if recipe.get("validation", {}).get("review_status") == "rejected":
        errors.append("/validation/review_status: rejected recipes cannot be compiled into build plans")

    if check_files:
        for pointer, reference in _file_refs(recipe):
            referenced = Path(_ref_path(reference))
            if not referenced.is_absolute():
                referenced = recipe_path.parent / referenced
            try:
                actual_hash = sha256(referenced.resolve(strict=True))
            except (OSError, RuntimeError):
                errors.append(f"{pointer}/path: referenced file does not exist or cannot be read")
                continue
            if actual_hash != reference["sha256"]:
                errors.append(f"{pointer}/sha256: checksum does not match referenced file")

    return sorted(set(errors))


def compile_build_plan(recipe: dict[str, Any], recipe_path: Path) -> dict[str, Any]:
    recipe_hash = sha256(recipe_path)
    schema_hash = sha256(SCHEMA_PATH)
    builder_path = ROOT / "tools/characters/compile_model_build_plan.py"
    compiler_hash = sha256(builder_path)
    source_files = []
    for pointer, reference in _file_refs(recipe):
        path = Path(_ref_path(reference))
        if not path.is_absolute():
            path = recipe_path.parent / path
        source_files.append({
            "recipe_pointer": pointer,
            "path": _ref_path(reference),
            "sha256": reference["sha256"],
        })
    rights_pending = [
        source.get("reference", "<unknown>")
        for source in recipe["provenance"]["sources"]
        if source["rights_status"] != "cleared"
    ]
    plan: dict[str, Any] = {
        "schema": PLAN_SCHEMA,
        "plan_state": "candidate_only",
        "recipe": {
            "recipe_id": recipe["recipe_id"],
            "revision": recipe["revision"],
            "schema": recipe["schema"],
            "sha256": recipe_hash,
            "snapshot": recipe,
        },
        "contract": {"path": "specs/atlas-model-recipe-v1.schema.json", "sha256": schema_hash},
        "compiler": {"path": "tools/characters/compile_model_build_plan.py", "sha256": compiler_hash},
        "builder": recipe["geometry"]["builder"],
        "geometry": {
            "method": recipe["geometry"]["method"],
            "resolution": recipe["geometry"].get("resolution", {}),
            "topology": recipe["geometry"]["topology"],
            "surface_regions": recipe["geometry"]["surface_regions"],
        },
        "dimensions": recipe["dimensions"],
        "components": recipe["components"],
        "materials": recipe["materials"],
        "material_assignments": recipe["material_assignments"],
        "rigging": recipe["rigging"],
        "performance_budget": recipe["performance_budget"],
        "inputs": sorted(source_files, key=lambda item: (item["recipe_pointer"], item["path"])),
        "gates": {
            "required_next_review": "geometry",
            "texture_generation_allowed_before_mesh_approval": False,
            "runtime_release_allowed": False,
            "rights_review_required_for_release": rights_pending,
        },
    }
    plan["plan_sha256"] = canonical_hash(plan)
    return plan
