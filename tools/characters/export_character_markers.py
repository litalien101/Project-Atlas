"""Export moved Blender marker guides after base acceptance."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from character_quality import is_rigging_candidate  # noqa: E402


MARKER_PREFIX = "ATLAS_MARKER_"
REQUIRED_MARKERS = {
    "ROOT", "SPINE_LOWER", "SPINE_UPPER", "NECK", "HEAD", "CROWN",
    "EYE_LEFT", "EYE_RIGHT", "EYEBROW_LEFT", "EYEBROW_RIGHT", "NOSE",
    "COLLARBONE_LEFT", "COLLARBONE_RIGHT",
    "SHOULDER_LEFT", "ELBOW_LEFT", "WRIST_LEFT", "SHOULDER_RIGHT", "ELBOW_RIGHT",
    "WRIST_RIGHT", "HAND_LEFT", "HIP_LEFT", "KNEE_LEFT", "ANKLE_LEFT",
    "HIP_RIGHT", "KNEE_RIGHT", "ANKLE_RIGHT", "HAND_RIGHT",
}


def arguments() -> argparse.Namespace:
    if "--" not in sys.argv:
        raise SystemExit("Pass marker-export options after --.")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blend", type=Path, required=True)
    parser.add_argument("--character-record", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])


def main() -> None:
    args = arguments()
    try:
        record = json.loads(args.character_record.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Cannot read character review record: {error}") from error
    if not is_rigging_candidate(record):
        raise RuntimeError(
            "Rig markers require a connected base accepted for rig authoring after a recorded sculpt review. "
            "This gate does not approve production or runtime use."
        )
    files = record.get("files")
    hashes = record.get("sha256")
    if not isinstance(files, dict) or not isinstance(hashes, dict):
        raise RuntimeError("Rig markers require a complete, checksum-bearing base review record")
    preview_name = files.get("preview_glb")
    expected_preview_hash = hashes.get("preview_glb")
    if not isinstance(preview_name, str) or not expected_preview_hash:
        raise RuntimeError("Rig markers require a preview GLB with a recorded SHA-256 checksum")
    preview = args.character_record.parent / preview_name
    if not preview.is_file() or hashlib.sha256(preview.read_bytes()).hexdigest() != expected_preview_hash:
        raise RuntimeError("Rig markers require the unchanged preview GLB that was reviewed for the base-mesh gate")
    bpy.ops.wm.open_mainfile(filepath=str(args.blend.resolve()))
    root = bpy.data.objects.get("ATLAS_GENERATED_CHARACTER_ROOT")
    if root is None:
        raise RuntimeError("Generated Blender file is missing ATLAS_GENERATED_CHARACTER_ROOT")
    inverse_root = root.matrix_world.inverted()
    markers = {}
    for obj in bpy.data.objects:
        if not obj.name.startswith(MARKER_PREFIX) or obj.type != "EMPTY":
            continue
        root_local = inverse_root @ obj.matrix_world.translation
        # The generated root carries the requested character-height scale.
        # Apply it here so exported coordinates are actual meters and can be
        # consumed directly by a later skeleton/weighting stage.
        markers[obj.name.removeprefix(MARKER_PREFIX)] = root.matrix_local.to_3x3() @ root_local
    missing = sorted(REQUIRED_MARKERS - set(markers))
    if missing:
        raise RuntimeError(f"Missing required rig markers: {', '.join(missing)}")
    payload = {
        "schema": "atlas-rig-landmarks/v1",
        "character_id": record["character_id"],
        "approval_scope": "rig_authoring_candidate_only",
        "coordinate_frame": "ATLAS_GENERATED_CHARACTER_ROOT local meters, Z up; root scale applied",
        "source_base_review_sha256": record["sha256"]["preview_glb"],
        "marker_status": "placement_exported_review_required",
        "markers": {
            name.lower(): [round(component, 6) for component in position]
            for name, position in sorted(markers.items())
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Exported {len(markers)} rig marker positions to {args.output}")
    print("Marker positions are an input to rig generation; this does not approve the rig or weights.")


if __name__ == "__main__":
    main()
