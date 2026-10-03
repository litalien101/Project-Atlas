"""Export moved Blender marker guides after base acceptance."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


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
    if record.get("base_review_status") != "accepted":
        raise RuntimeError("Accept the base model before exporting rig markers")
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
