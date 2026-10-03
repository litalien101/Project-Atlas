"""RETIRED: build a rig-weighted region map for the removed female base.

Run from the project root with the repository's pinned Blender version:
  blender --background --python tools/characters/build_body_region_schema.py

The resulting polygon indices are valid only for the recorded source GLB hash.
Small placement landmarks such as eyebrow outlines still require authored data.

See tools/characters/README.md. This script is retained for historical review
and refuses direct execution.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[2]
BLEND = ROOT / "art/characters/atlas_female_base_v1/atlas_female_base_v1.blend"
BASE_GLB = ROOT / "web/assets/characters/female_base_atlas_v1.glb"
RIG_JSON = ROOT / "art/characters/atlas_humanoid_v1/atlas_humanoid_v1.json"
OUTPUT = ROOT / "art/characters/atlas_female_base_v1/atlas_body_regions_v1.json"
BODY_OBJECT = "ATLAS_FEMALE_BODY_V1"

REGION_BONES = {
    "head": {"head", "neck", "lefteye", "righteye", "headtopend"},
    "torso": {"hips", "spine", "spine1", "spine2"},
    "left_arm": {"leftshoulder", "leftarm", "leftforearm"},
    "right_arm": {"rightshoulder", "rightarm", "rightforearm"},
    "left_hand": {"lefthand"},
    "right_hand": {"righthand"},
    "left_leg": {"leftupleg", "leftleg"},
    "right_leg": {"rightupleg", "rightleg"},
    "left_foot": {"leftfoot", "lefttoebase", "lefttoeend"},
    "right_foot": {"rightfoot", "righttoebase", "righttoeend"},
}


def canonical(name: str) -> str:
    return "".join(character.lower() for character in name if character.isalnum()).removeprefix("mixamorig")


def main() -> None:
    bpy.ops.wm.open_mainfile(filepath=str(BLEND))
    body = bpy.data.objects.get(BODY_OBJECT)
    if body is None or body.type != "MESH":
        raise RuntimeError(f"Missing Atlas body mesh {BODY_OBJECT}")
    base_contract = json.loads((ROOT / "art/characters/atlas_female_base_v1/atlas_female_base_v1.json").read_text())
    rig_contract = json.loads(RIG_JSON.read_text())
    actual_base_hash = hashlib.sha256(BASE_GLB.read_bytes()).hexdigest()
    if actual_base_hash != base_contract["runtime_sha256"]:
        raise RuntimeError("Female base GLB checksum and character contract differ; rebuild the base contract first")
    if actual_base_hash != rig_contract["source_sha256"]:
        raise RuntimeError("Humanoid rig contract is stale; rebuild it before generating body regions")

    group_name_by_index = {group.index: group.name for group in body.vertex_groups}
    canonical_by_index = {index: canonical(name) for index, name in group_name_by_index.items()}
    region_for_bone = {
        bone: region for region, bones in REGION_BONES.items() for bone in bones
    }
    region_bone_names = {
        region: sorted(name for name in group_name_by_index.values()
                       if region_for_bone.get(canonical(name)) == region)
        for region in REGION_BONES
    }
    vertex_scores: list[dict[str, float]] = []
    region_vertices = {region: set() for region in REGION_BONES}
    for vertex in body.data.vertices:
        scores = {region: 0.0 for region in REGION_BONES}
        for assignment in vertex.groups:
            region = region_for_bone.get(canonical_by_index[assignment.group])
            if region:
                scores[region] += assignment.weight
        vertex_scores.append(scores)

    region_polygons = {region: [] for region in REGION_BONES}
    for polygon in body.data.polygons:
        averages = {
            region: sum(vertex_scores[index][region] for index in polygon.vertices) / len(polygon.vertices)
            for region in REGION_BONES
        }
        region, confidence = max(averages.items(), key=lambda item: item[1])
        if confidence < 0.5:
            continue
        region_polygons[region].append(polygon.index)
        region_vertices[region].update(polygon.vertices)

    regions = {}
    for region, polygon_ids in region_polygons.items():
        vertex_ids = sorted(region_vertices[region])
        coords = [body.data.vertices[index].co for index in vertex_ids]
        if not coords:
            raise RuntimeError(f"Body region {region} classified no vertices")
        regions[region] = {
            "classification": "dominant_skinning_influence",
            "minimum_region_weight": 0.5,
            "bone_names": region_bone_names[region],
            "polygon_indices": polygon_ids,
            "vertex_indices": vertex_ids,
            "bounds_local_m": {
                "minimum": [min(v[axis] for v in coords) for axis in range(3)],
                "maximum": [max(v[axis] for v in coords) for axis in range(3)],
            },
            "surface_landmarks": {},
        }

    result = {
        "schema": "atlas-body-regions/v1",
        "character_id": base_contract["asset_id"],
        "skeleton_id": rig_contract["skeleton_id"],
        "source_glb": "web/assets/characters/female_base_atlas_v1.glb",
        "source_sha256": actual_base_hash,
        "body_object": BODY_OBJECT,
        "coordinate_frame": {"units": "meters", "up_axis": "Z in Blender source", "forward_axis": "preserve base model"},
        "region_assignment": "For each polygon, assign the region with greatest average skinning influence; omit polygons below the confidence threshold.",
        "regions": regions,
        "landmark_policy": "Fine placement points (for example brow outlines, eye corners, lip line, wrist center) must be authored and reviewed separately; bounds are not placement anchors.",
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Wrote {OUTPUT}")
    for region, definition in regions.items():
        print(f"{region}: {len(definition['polygon_indices'])} polygons, {len(definition['vertex_indices'])} vertices")


if __name__ == "__main__":
    raise SystemExit("Retired: required source assets were removed. See tools/characters/README.md.")
