"""Re-export a reviewed Blender base without regenerating or resetting it."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/characters"))
from generate_character_base import (  # noqa: E402
    add_region_metadata,
    build_dimensions,
    export_static_preview,
)
from character_topology import TopologyValidationError, validate_shoulder_core  # noqa: E402


BODY_NAME = "ATLAS_PROCEDURAL_BODY_V1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blend", type=Path, required=True)
    parser.add_argument("--character-record", type=Path, required=True)
    args = parser.parse_args()
    blend_path = args.blend.resolve()
    record_path = args.character_record.resolve()
    record = json.loads(record_path.read_text(encoding="utf-8"))
    if record.get("base_review_status") == "accepted":
        raise RuntimeError("This base is already accepted; do not silently change the accepted review artifact")
    bpy.ops.wm.open_mainfile(filepath=str(blend_path))
    body = bpy.data.objects.get(BODY_NAME)
    if body is None or body.type != "MESH":
        raise RuntimeError(f"Edited Blender file is missing {BODY_NAME}")
    features = [obj for obj in bpy.data.objects if obj.name.startswith("ATLAS_FEATURE_") and obj.type == "MESH"]
    dimensions = build_dimensions(record["design_profile"])
    try:
        topology_report = validate_shoulder_core(
            [tuple(vertex.co) for vertex in body.data.vertices],
            [tuple(edge.vertices) for edge in body.data.edges],
            [tuple(polygon.vertices) for polygon in body.data.polygons],
            shoulder_height=dimensions["shoulder_z"],
            shoulder_half_width=dimensions["shoulder_half"],
        )
    except TopologyValidationError as error:
        print(str(error), file=sys.stderr, flush=True)
        sys.exit(1)
    regions_path = record_path.parent / record["files"]["body_regions"]
    region_data = add_region_metadata(body, dimensions)
    regions_path.write_text(json.dumps(region_data, indent=2) + "\n", encoding="utf-8")
    body["atlas.shoulder_core_connected"] = True
    body["atlas.topology_report"] = json.dumps(topology_report, sort_keys=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    preview = record_path.parent / record["files"]["preview_glb"]
    export_static_preview(body, features, preview)
    record["sha256"]["blend"] = sha256(blend_path)
    record["sha256"]["preview_glb"] = sha256(preview)
    record["sha256"]["body_regions"] = sha256(regions_path)
    record["mesh"]["vertex_count"] = len(body.data.vertices)
    record["mesh"]["polygon_count"] = len(body.data.polygons)
    record["mesh"]["shoulder_core_connected"] = topology_report["shoulder_core_connected"]
    record["mesh"]["topology_validation"] = topology_report
    record["base_review_status"] = "review_required"
    record["pipeline_stage"] = "base_generated"
    record["next_stage"] = "human_review_base"
    record.pop("base_review", None)
    record_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"Refreshed static preview: {preview}")
    print("Human acceptance is still required before rig-marker export.")


if __name__ == "__main__":
    main()
