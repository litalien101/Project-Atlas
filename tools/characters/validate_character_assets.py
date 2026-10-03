"""Validate Atlas runtime character assets and their provenance records.

Run from the project root:
  python3 tools/characters/validate_character_assets.py
  python3 tools/characters/validate_character_assets.py --release

The release mode also fails when redistribution rights are not explicitly
cleared. This validator checks file integrity and glTF structure; it does not
replace the required in-engine animation and visual review.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "web/assets/manifest.yaml"
SHA256_LENGTH = 64
REQUIRED_FIT_REVIEW_CHECKS = {
    "idle", "walk", "run", "jump", "fall", "land", "morph_low", "morph_high",
    "silhouette", "hem_and_armholes", "clipping", "deformation", "disconnected_parts",
}


class ValidationError(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_glb(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    require(len(data) >= 20, f"{path.relative_to(ROOT)}: file is too short to be GLB")
    magic, version, declared_length = struct.unpack_from("<4sII", data)
    require(magic == b"glTF", f"{path.relative_to(ROOT)}: invalid GLB magic")
    require(version == 2, f"{path.relative_to(ROOT)}: expected glTF 2.0, got {version}")
    require(declared_length == len(data), f"{path.relative_to(ROOT)}: GLB length header does not match file size")

    offset = 12
    document = None
    while offset < len(data):
        require(offset + 8 <= len(data), f"{path.relative_to(ROOT)}: truncated GLB chunk header")
        chunk_length, chunk_type = struct.unpack_from("<I4s", data, offset)
        offset += 8
        end = offset + chunk_length
        require(end <= len(data), f"{path.relative_to(ROOT)}: truncated GLB chunk")
        if chunk_type == b"JSON":
            try:
                document = json.loads(data[offset:end].decode("utf-8").rstrip(" \t\r\n\0"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise ValidationError(f"{path.relative_to(ROOT)}: invalid glTF JSON: {error}") from error
        offset = end
    require(isinstance(document, dict), f"{path.relative_to(ROOT)}: missing JSON chunk")
    return document


def accessor_count(document: dict[str, Any], accessor_index: int, label: str) -> int:
    accessors = document.get("accessors", [])
    require(isinstance(accessor_index, int) and 0 <= accessor_index < len(accessors),
            f"{label}: invalid accessor index {accessor_index}")
    accessor = accessors[accessor_index]
    count = accessor.get("count")
    require(isinstance(count, int) and count > 0, f"{label}: accessor must have a positive count")
    return count


def validate_skinned_glb(path: Path, expected_bones: list[dict[str, Any]]) -> None:
    document = read_glb(path)
    skins = document.get("skins", [])
    require(len(skins) == 1, f"{path.relative_to(ROOT)}: expected one shared character skin, found {len(skins)}")
    skin = skins[0]
    joints = skin.get("joints", [])
    require(len(joints) == len(expected_bones),
            f"{path.relative_to(ROOT)}: expected {len(expected_bones)} joints, found {len(joints)}")
    nodes = document.get("nodes", [])
    require(all(isinstance(index, int) and 0 <= index < len(nodes) for index in joints),
            f"{path.relative_to(ROOT)}: skin references an invalid joint node")
    joint_names = [nodes[index].get("name") for index in joints]
    require(all(isinstance(name, str) and name for name in joint_names),
            f"{path.relative_to(ROOT)}: all joint nodes must have stable names")
    require(len(set(joint_names)) == len(joint_names), f"{path.relative_to(ROOT)}: joint names are not unique")
    expected_hierarchy = {bone["name"]: bone["parent"] for bone in expected_bones}
    require(set(joint_names) == set(expected_hierarchy),
            f"{path.relative_to(ROOT)}: joint names do not match the versioned Atlas rig")
    node_by_name = {nodes[index].get("name"): index for index in joints}
    parent_by_node = {
        child: parent
        for parent, node in enumerate(nodes)
        for child in node.get("children", [])
    }
    for name, joint_index in node_by_name.items():
        ancestor = parent_by_node.get(joint_index)
        while ancestor is not None and nodes[ancestor].get("name") not in expected_hierarchy:
            ancestor = parent_by_node.get(ancestor)
        actual_parent = nodes[ancestor].get("name") if ancestor is not None else None
        require(actual_parent == expected_hierarchy[name],
                f"{path.relative_to(ROOT)}: {name} parent is {actual_parent!r}, expected {expected_hierarchy[name]!r}")

    mesh_count = 0
    for mesh_index, mesh in enumerate(document.get("meshes", [])):
        for primitive_index, primitive in enumerate(mesh.get("primitives", [])):
            attributes = primitive.get("attributes", {})
            label = f"{path.relative_to(ROOT)} mesh {mesh_index} primitive {primitive_index}"
            require("JOINTS_0" in attributes and "WEIGHTS_0" in attributes,
                    f"{label}: expected skin joint and weight attributes")
            position_count = accessor_count(document, attributes.get("POSITION"), label)
            for attribute in ("JOINTS_0", "WEIGHTS_0"):
                count = accessor_count(document, attributes[attribute], label)
                require(count == position_count, f"{label}: {attribute} count does not match POSITION")
            mesh_count += 1
    require(mesh_count > 0, f"{path.relative_to(ROOT)}: no skinned mesh primitives found")


def manifest_entries() -> list[dict[str, Any]]:
    try:
        parsed = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ValidationError(f"Cannot read asset manifest: {error}") from error
    require(isinstance(parsed, list), "Asset manifest must be a YAML list")
    ids: set[str] = set()
    paths: set[str] = set()
    for entry in parsed:
        require(isinstance(entry, dict), "Every manifest entry must be a mapping")
        asset_id = entry.get("id")
        require(isinstance(asset_id, str) and asset_id.strip(), "Every manifest entry needs a stable id")
        require(asset_id not in ids, f"Duplicate manifest asset id: {asset_id}")
        ids.add(asset_id)
        files = entry.get("files")
        require(isinstance(files, list) and files, f"{asset_id}: files must be a non-empty list")
        for relative in files:
            require(isinstance(relative, str) and relative and "\\" not in relative,
                    f"{asset_id}: invalid asset path {relative!r}")
            candidate = (ROOT / "web/assets" / relative).resolve()
            require(candidate.is_relative_to((ROOT / "web/assets").resolve()),
                    f"{asset_id}: asset path escapes web/assets: {relative}")
            require(relative not in paths, f"Asset file is registered more than once: {relative}")
            paths.add(relative)
    return parsed


def validate_manifest(entry_list: list[dict[str, Any]], release: bool) -> list[str]:
    warnings: list[str] = []
    for entry in entry_list:
        asset_id = entry["id"]
        files = entry["files"]
        checksums = entry.get("checksum_sha256")
        require(isinstance(checksums, dict), f"{asset_id}: checksum_sha256 must map each file to its digest")
        require(set(checksums) == set(files), f"{asset_id}: checksum list must match the registered files exactly")
        for relative in files:
            path = (ROOT / "web/assets" / relative).resolve()
            require(path.is_file(), f"{asset_id}: missing asset file {relative}")
            expected = checksums[relative]
            require(isinstance(expected, str) and len(expected) == SHA256_LENGTH,
                    f"{asset_id}: invalid SHA-256 for {relative}")
            actual = sha256(path)
            require(actual == expected.lower(),
                    f"{asset_id}: checksum mismatch for {relative}; expected {expected}, got {actual}")
            if path.suffix.lower() == ".glb":
                skeleton = entry.get("skeleton_contract")
                if skeleton:
                    require(isinstance(skeleton, str), f"{asset_id}: skeleton_contract must name a JSON file")
                    contract_path = (ROOT / skeleton).resolve()
                    require(contract_path.is_relative_to(ROOT.resolve()) and contract_path.is_file(),
                            f"{asset_id}: missing or unsafe skeleton contract {skeleton}")
                    contract = json.loads(contract_path.read_text(encoding="utf-8"))
                    require(isinstance(contract.get("bones"), list),
                            f"{asset_id}: skeleton contract has no bones list")
                    validate_skinned_glb(path, contract["bones"])

        license_text = str(entry.get("license", "")).lower()
        rights = entry.get("redistribution_status")
        cleared = rights == "cleared" and "undocumented" not in license_text and "review_required" not in license_text
        if not cleared:
            message = f"{asset_id}: redistribution rights are not marked cleared"
            if release:
                raise ValidationError(message)
            warnings.append(message)
        if entry.get("asset_kind") == "clothing":
            approved = entry.get("fit_review_status") == "approved"
            if not approved:
                message = f"{asset_id}: clothing has not passed visual fit and animation review"
                if release:
                    raise ValidationError(message)
                warnings.append(message)
            require(entry.get("skeleton_id") == "ATLAS_HUMANOID_V1",
                    f"{asset_id}: clothing targets an unsupported skeleton")
            require(isinstance(entry.get("fit_reviewer"), str) and bool(entry["fit_reviewer"].strip()) if approved else True,
                    f"{asset_id}: approved clothing has no named fit reviewer")
            require(isinstance(entry.get("fit_review_checklist"), dict) and all(
                value is True for value in entry["fit_review_checklist"].values())
                    and set(entry["fit_review_checklist"]) == REQUIRED_FIT_REVIEW_CHECKS if approved else True,
                f"{asset_id}: approved clothing has incomplete review evidence")
    return warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", action="store_true", help="Fail unless every asset's redistribution status is cleared")
    args = parser.parse_args()
    try:
        warnings = validate_manifest(manifest_entries(), args.release)
    except ValidationError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print("PASS: registered asset paths and checksums are valid; GLB skeletons are checked when a contract is declared")
    for warning in warnings:
        print(f"REVIEW: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
