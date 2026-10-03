"""Admit a reviewed pending clothing GLB to the runtime asset registry.

This operation requires explicit reviewer and redistribution-rights metadata;
it never turns a prepared asset into a runtime asset automatically.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_character_assets import ValidationError, read_glb, validate_skinned_glb  # noqa: E402


CHECKS = {
    "idle", "walk", "run", "jump", "fall", "land", "morph_low", "morph_high",
    "silhouette", "hem_and_armholes", "clipping", "deformation", "disconnected_parts",
}
SLOTS = {"underwear_top", "underwear_bottom", "head", "hair", "face", "neck", "shoulders",
         "cape", "chest", "gloves", "belt", "legs", "socks", "boots", "main_hand", "off_hand"}


def fail(message: str) -> None:
    raise ValueError(message)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", required=True, type=Path, help="Metadata JSON from prepare_clothing_asset.py")
    parser.add_argument("--glb", required=True, type=Path, help="Prepared GLB under art/characters/pending_equipment")
    parser.add_argument("--creator", required=True)
    parser.add_argument("--license", required=True, help="Exact applicable license or rights statement")
    parser.add_argument("--license-evidence", required=True, help="Source, URL, or written permission reference")
    parser.add_argument("--rights-reviewed", action="store_true", required=True,
                        help="Attest that the supplied license evidence clears redistribution")
    parser.add_argument("--reviewer", required=True, help="Human who completed the visual fit review")
    parser.add_argument("--checklist", required=True, type=Path,
                        help="JSON object with all 13 required checks set to true")
    args = parser.parse_args()

    try:
        meta_path = args.metadata.resolve(strict=True)
        glb_path = args.glb.resolve(strict=True)
        if not meta_path.is_relative_to((ROOT / "art/characters/pending_equipment").resolve()):
            fail("Metadata must remain under art/characters/pending_equipment until registration.")
        if not glb_path.is_relative_to((ROOT / "art/characters/pending_equipment").resolve()):
            fail("GLB must remain under art/characters/pending_equipment until registration.")
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        checklist = json.loads(args.checklist.read_text(encoding="utf-8"))
        if metadata.get("schema") != "atlas-equipment/v1" or metadata.get("fit_review_status") != "review_required":
            fail("The GLB does not have pending Atlas equipment metadata.")
        if metadata.get("skeleton_id") != "ATLAS_HUMANOID_V1":
            fail("Only ATLAS_HUMANOID_V1 equipment may be registered here.")
        asset_id = metadata.get("asset_id")
        slot = metadata.get("equipment_slot")
        if not isinstance(asset_id, str) or not re.fullmatch(r"atlas\.[a-z0-9_.-]+", asset_id):
            fail("Metadata contains an invalid stable asset ID.")
        if slot not in SLOTS:
            fail("Metadata contains an unsupported equipment slot.")
        if not isinstance(args.creator, str) or not args.creator.strip() or not args.license.strip() or not args.license_evidence.strip():
            fail("Creator, license, and license evidence must be non-empty.")
        if not isinstance(args.reviewer, str) or not args.reviewer.strip():
            fail("A named human reviewer is required.")
        if not isinstance(checklist, dict) or set(checklist) != CHECKS or any(checklist[key] is not True for key in CHECKS):
            fail("Fit checklist must contain every required check, each set to true.")
        digest = hashlib.sha256(glb_path.read_bytes()).hexdigest()
        if metadata.get("runtime_sha256") != digest:
            fail("Prepared GLB checksum does not match its metadata.")
        source_value = metadata.get("source_blend")
        if isinstance(source_value, str):
            source_path = Path(source_value)
            if source_path.is_absolute():
                try:
                    source_value = source_path.resolve().relative_to(ROOT).as_posix()
                except ValueError:
                    fail("Source Blender file must be inside the Project Atlas checkout.")

        rig = json.loads((ROOT / "art/characters/atlas_humanoid_v1/atlas_humanoid_v1.json").read_text())
        validate_skinned_glb(glb_path, rig["bones"])
        manifest_path = ROOT / "web/assets/manifest.yaml"
        entries = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(entries, list) or any(item.get("asset_id") == asset_id or item.get("id") == asset_id for item in entries):
            fail("Asset ID is invalid or already registered.")
        filename = asset_id.removeprefix("atlas.clothing.").replace(".", "_") + ".glb"
        relative = f"clothing/{filename}"
        destination = ROOT / "web/assets" / relative
        if destination.exists():
            fail(f"Runtime asset already exists: {relative}")
        entry = {
            "id": asset_id,
            "asset_kind": "clothing",
            "asset_id": asset_id,
            "files": [relative],
            "creator": args.creator.strip(),
            "source": source_value,
            "license": args.license.strip(),
            "license_evidence": args.license_evidence.strip(),
            "redistribution_status": "cleared",
            "fit_review_status": "approved",
            "fit_reviewer": args.reviewer.strip(),
            "fit_review_completed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "fit_review_checklist": checklist,
            "checksum_sha256": {relative: digest},
            "skeleton_id": metadata["skeleton_id"],
            "equipment_slots": [slot],
            "body_regions": metadata.get("body_regions", []),
            "body_region_schema": metadata.get("body_region_schema"),
            "modifications": "Prepared with the Atlas clothing pipeline; see equipment metadata and review checklist.",
        }
        entries.append(entry)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary_asset = destination.with_suffix(".glb.pending")
        shutil.copy2(glb_path, temporary_asset)
        temporary_manifest = manifest_path.with_suffix(".yaml.pending")
        temporary_manifest.write_text(yaml.safe_dump(entries, sort_keys=False, allow_unicode=True), encoding="utf-8")
        temporary_asset.replace(destination)
        temporary_manifest.replace(manifest_path)
    except (OSError, json.JSONDecodeError, yaml.YAMLError, ValidationError, ValueError) as error:
        print(f"Registration refused: {error}", file=sys.stderr)
        return 1
    print(f"Registered reviewed clothing asset {asset_id} at web/assets/{relative}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
