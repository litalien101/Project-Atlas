"""Extract normalized shape and rig measurements from a GLB or Blender reference.

Run with Blender:
  blender --background --python tools/characters/calibrate_character_reference.py -- \
    --source /path/to/rights-cleared-reference.glb \
    --output art/characters/references/calibrations/reference_id.json

For .blend sources also pass --object-name and source provenance flags. This
records measurements and provenance; it does not grant geometry-seed approval
or copy content into runtime assets. A separate human review and profile
attestation are required before the builder can use the source geometry.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[2]


def arguments() -> argparse.Namespace:
    if "--" not in sys.argv:
        raise SystemExit("Pass options after --. See the script header.")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--object-name", help="Exact source mesh object; required for .blend files and multi-mesh GLBs.")
    parser.add_argument("--source-title", help="Source title (required for .blend files without embedded provenance).")
    parser.add_argument("--source-author", help="Creator name (required for .blend files without embedded provenance).")
    parser.add_argument("--source-license", help="Exact license label (required for .blend files without embedded provenance).")
    parser.add_argument("--source-url", help="Original source page URL (required for .blend files without embedded provenance).")
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])


def read_glb_metadata(path: Path) -> dict:
    data = path.read_bytes()
    if len(data) < 20:
        raise ValueError("File is too small to be a GLB.")
    magic, version, declared_length = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF" or version != 2 or declared_length != len(data):
        raise ValueError("Expected a complete glTF 2.0 binary (.glb).")
    json_length, chunk_type = struct.unpack_from("<I4s", data, 12)
    if chunk_type != b"JSON":
        raise ValueError("GLB has no leading JSON metadata chunk.")
    document = json.loads(data[20 : 20 + json_length])
    asset = document.get("asset", {})
    return {
        "generator": asset.get("generator"),
        "title": asset.get("extras", {}).get("title"),
        "author": asset.get("extras", {}).get("author"),
        "license": asset.get("extras", {}).get("license"),
        "source": asset.get("extras", {}).get("source"),
        "glb_mesh_count": len(document.get("meshes", [])),
        "glb_skin_count": len(document.get("skins", [])),
        "glb_animation_names": [item.get("name", "unnamed") for item in document.get("animations", [])],
    }


def v3(value: Vector) -> list[float]:
    return [round(float(component), 6) for component in value]


def main() -> None:
    args = arguments()
    source = args.source.expanduser().resolve(strict=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    if source.suffix.lower() == ".glb":
        metadata = read_glb_metadata(source)
        bpy.ops.import_scene.gltf(filepath=str(source))
    elif source.suffix.lower() == ".blend":
        if not args.object_name:
            raise ValueError("Pass --object-name for a Blender source so calibration cannot select an unrelated mesh.")
        if not all((args.source_title, args.source_author, args.source_license, args.source_url)):
            raise ValueError("Blender sources require --source-title, --source-author, --source-license, and --source-url provenance.")
        bpy.ops.wm.open_mainfile(filepath=str(source))
        metadata = {
            "generator": "Blender source project",
            "title": args.source_title,
            "author": args.source_author,
            "license": args.source_license,
            "source": args.source_url,
            "glb_mesh_count": None,
            "glb_skin_count": None,
            "glb_animation_names": [],
        }
    else:
        raise ValueError("Calibration accepts a .glb or .blend source file.")

    if args.source_title:
        metadata["title"] = args.source_title
    if args.source_author:
        metadata["author"] = args.source_author
    if args.source_license:
        metadata["license"] = args.source_license
    if args.source_url:
        metadata["source"] = args.source_url

    depsgraph = bpy.context.evaluated_depsgraph_get()
    mesh_measurements = []
    for obj in (item for item in bpy.context.scene.objects if item.type == "MESH"):
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        if len(mesh.vertices) < 100:
            evaluated.to_mesh_clear()
            continue
        points = [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
        evaluated.to_mesh_clear()
        low = Vector(tuple(min(point[axis] for point in points) for axis in range(3)))
        high = Vector(tuple(max(point[axis] for point in points) for axis in range(3)))
        mesh_measurements.append((len(points), obj, points, low, high))
    if not mesh_measurements:
        raise ValueError("No substantial mesh object found in reference GLB.")
    if args.object_name:
        selected = next((row for row in mesh_measurements if row[1].name == args.object_name), None)
        if selected is None:
            available = ", ".join(row[1].name for row in mesh_measurements)
            raise ValueError(f"Source mesh {args.object_name!r} was not found among substantial meshes: {available}")
        selected_row = selected
    else:
        mesh_measurements.sort(key=lambda row: row[0], reverse=True)
        selected_row = mesh_measurements[0]
    _, body_obj, points, low, high = selected_row
    height = high.z - low.z
    if height <= 1e-6:
        raise ValueError("Reference mesh has no measurable vertical extent.")

    # Evenly spaced slices provide a reusable shape signature, not an assertion
    # that every genre or anatomy should match this one exemplar.
    slices = []
    for percent in range(5, 100, 5):
        z = low.z + height * percent / 100
        band = [point for point in points if abs(point.z - z) <= height * 0.0125]
        if len(band) < 8:
            continue
        xs = sorted(point.x for point in band)
        ys = sorted(point.y for point in band)
        def quantile(values: list[float], q: float) -> float:
            return values[min(len(values) - 1, round((len(values) - 1) * q))]
        slices.append({
            "height_percent": percent,
            "sample_vertices": len(band),
            "x_extent_over_height": round((quantile(xs, .98) - quantile(xs, .02)) / height, 6),
            "y_extent_over_height": round((quantile(ys, .98) - quantile(ys, .02)) / height, 6),
            "center_x_over_height": round((quantile(xs, .50) - (low.x + high.x) / 2) / height, 6),
            "center_y_over_height": round((quantile(ys, .50) - (low.y + high.y) / 2) / height, 6),
        })

    armatures = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    landmarks = {}
    if armatures:
        armature = max(armatures, key=lambda obj: len(obj.data.bones))
        aliases = {
            "pelvis": ("hip",), "spine": ("spine",), "chest": ("chest",),
            "neck": ("neck",), "head": ("head",), "left_shoulder": ("l_shoulder", "left_shoulder"),
            "right_shoulder": ("r_shoulder", "right_shoulder"),
            "left_elbow": ("l_elbow", "left_elbow"), "right_elbow": ("r_elbow", "right_elbow"),
            "left_wrist": ("l_wrist", "left_wrist"), "right_wrist": ("r_wrist", "right_wrist"),
            "left_knee": ("l_knee", "left_knee"), "right_knee": ("r_knee", "right_knee"),
            "left_ankle": ("l_ankle", "left_ankle"), "right_ankle": ("r_ankle", "right_ankle"),
            "left_eye": ("l_eye", "left_eye"), "right_eye": ("r_eye", "right_eye"), "jaw": ("jaw",),
        }
        bone_map = {bone.name.lower(): bone for bone in armature.data.bones}
        for label, tokens in aliases.items():
            bone = next((bone for name, bone in bone_map.items() if any(token in name for token in tokens)), None)
            if bone is None:
                continue
            point = armature.matrix_world @ bone.head_local
            landmarks[label] = {
                "source_bone": bone.name,
                "position": v3(point),
                "height_percent": round((point.z - low.z) / height * 100, 3),
                "centered_x_over_height": round((point.x - (low.x + high.x) / 2) / height, 6),
                "centered_y_over_height": round((point.y - (low.y + high.y) / 2) / height, 6),
            }

    record = {
        "schema": "atlas-character-reference-calibration/v1",
        "calibrated_at": datetime.now(timezone.utc).isoformat(),
        "source_file": source.name,
        "source_path_from_project_root": os.path.relpath(source, ROOT),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "provenance": metadata,
        "measurement_method": "Blender GLB import; evaluated mesh world-space bounds; robust 2-percentile cross-sections; source rest-pose bone heads.",
        "limitations": [
            "Measurements describe this reference only; its rest pose and rig are not Atlas-compatible by implication.",
            "Cross-sections summarize the whole surface at each height and may include arms, ears, or other protrusions.",
            "Use the record to tune and compare the procedural recipe; do not copy geometry, textures, rig, or animation without separate review.",
        ],
        "geometry": {
            "selected_mesh_object": body_obj.name,
            "selected_mesh_vertex_count": len(points),
            "low": v3(low), "high": v3(high),
            "height": round(height, 6),
            "width_over_height": round((high.x - low.x) / height, 6),
            "depth_over_height": round((high.y - low.y) / height, 6),
            "other_substantial_mesh_objects": [
                {"name": obj.name, "vertex_count": count}
                for count, obj, _, _, _ in mesh_measurements[1:]
            ],
            "cross_sections": slices,
        },
        "rig": {
            "armature_count": len(armatures),
            "selected_armature": max(armatures, key=lambda obj: len(obj.data.bones)).name if armatures else None,
            "bone_count": max((len(obj.data.bones) for obj in armatures), default=0),
            "landmarks": landmarks,
        },
    }
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"Reference calibration: {output}")
    print(f"Source: {metadata.get('title')} by {metadata.get('author')} ({metadata.get('license')})")
    print(f"Measured body: {body_obj.name}, height {height:.2f}, width/height {record['geometry']['width_over_height']:.3f}, depth/height {record['geometry']['depth_over_height']:.3f}")
    print(f"Cross-sections: {len(slices)}; rig landmarks: {len(landmarks)}")


if __name__ == "__main__":
    main()
