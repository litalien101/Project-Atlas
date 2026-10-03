"""PAUSED: prepare a modeled garment against the removed female base and rig.

Run from the project root with:
  blender --background --python tools/characters/prepare_clothing_asset.py -- \
    --blend /path/to/garment_working_copy.blend --garment shirt_basic \
    --slot chest --asset-id atlas.clothing.shirt_basic_v1

The working file must contain ATLAS_FEMALE_BODY_V1, the Atlas armature, and the
artist-modeled garment mesh. The source file is not overwritten.

See tools/characters/README.md. This legacy workflow is unsupported until a new
licensed, reviewed base and rig contract exists; direct execution is disabled.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


ROOT = Path(__file__).resolve().parents[2]
BODY_NAME = "ATLAS_FEMALE_BODY_V1"
RIG_NAME = "ATLAS_HUMANOID_V1_RIG"
REGION_SCHEMA_PATH = ROOT / "art/characters/atlas_female_base_v1/atlas_body_regions_v1.json"
REGION_SCHEMA = json.loads(REGION_SCHEMA_PATH.read_text(encoding="utf-8"))
EQUIPMENT_SLOTS = {
    "underwear_top", "underwear_bottom", "head", "hair", "face", "neck",
    "shoulders", "cape", "chest", "gloves", "belt", "legs", "socks",
    "boots", "main_hand", "off_hand",
}
SLOT_REGIONS = {
    "underwear_top": {"torso"}, "underwear_bottom": {"torso", "left_leg", "right_leg"},
    "head": {"head"}, "hair": {"head"}, "face": {"head"}, "neck": {"head", "torso"},
    "shoulders": {"torso", "left_arm", "right_arm"}, "cape": {"torso"},
    "chest": {"torso", "left_arm", "right_arm"},
    "gloves": {"left_hand", "right_hand"}, "belt": {"torso"}, "legs": {"torso", "left_leg", "right_leg"},
    "socks": {"left_leg", "right_leg", "left_foot", "right_foot"},
    "boots": {"left_foot", "right_foot"}, "main_hand": {"right_hand"}, "off_hand": {"left_hand"},
}


def arguments() -> argparse.Namespace:
    if "--" not in sys.argv:
        raise SystemExit("Pass script options after --. See the script header for an example.")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blend", required=True, type=Path, help="Artist working .blend containing the base, rig, and garment")
    parser.add_argument("--body", default=BODY_NAME, help=f"Body mesh object name (default: {BODY_NAME})")
    parser.add_argument("--rig", default=RIG_NAME, help=f"Armature object name (default: {RIG_NAME})")
    parser.add_argument("--garment", required=True, help="Mesh object name to prepare")
    parser.add_argument("--slot", required=True, help="Stable equipment slot, such as chest, gloves, or boots")
    parser.add_argument("--region", required=True, action="append", choices=sorted(REGION_SCHEMA["regions"]),
                        help="Body region(s) this garment covers; repeat for multi-region assets")
    parser.add_argument("--asset-id", required=True, help="Stable registry ID, such as atlas.clothing.shirt_basic_v1")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "art/characters/pending_equipment")
    parser.add_argument("--max-body-offset", type=float, default=0.12,
                        help="Fail if any garment vertex is farther than this many meters from the declared body regions")
    parser.add_argument("--exclude-bone", action="append", default=[], help="Optional bone group to omit; may be repeated")
    parser.add_argument("--max-influences", type=int, default=4, choices=range(1, 5),
                        help="Maximum skin influences per vertex (glTF v1 contract caps this at four)")
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])


def set_active(obj: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def apply_authoring_modifiers(garment: bpy.types.Object) -> None:
    """Bake topology-changing artist modifiers before adding matching morphs."""
    if garment.data.shape_keys:
        keys = garment.data.shape_keys.key_blocks
        for key in list(keys)[1:]:
            garment.shape_key_remove(key)
        if garment.data.shape_keys and garment.data.shape_keys.key_blocks:
            garment.shape_key_remove(garment.data.shape_keys.key_blocks[0])
    set_active(garment)
    for modifier in list(garment.modifiers):
        if modifier.type == "ARMATURE":
            garment.modifiers.remove(modifier)
            continue
        bpy.ops.object.modifier_apply(modifier=modifier.name)


def barycentric(point: Vector, a: Vector, b: Vector, c: Vector) -> tuple[float, float, float]:
    ab, ac, ap = b - a, c - a, point - a
    d00, d01, d11 = ab.dot(ab), ab.dot(ac), ac.dot(ac)
    d20, d21 = ap.dot(ab), ap.dot(ac)
    denominator = d00 * d11 - d01 * d01
    if abs(denominator) < 1e-12:
        return (1.0, 0.0, 0.0)
    v = (d11 * d20 - d01 * d21) / denominator
    w = (d00 * d21 - d01 * d20) / denominator
    values = [max(0.0, 1.0 - v - w), max(0.0, v), max(0.0, w)]
    total = sum(values)
    return tuple(value / total for value in values) if total else (1.0, 0.0, 0.0)


def body_surface_map(body: bpy.types.Object, garment: bpy.types.Object,
                     allowed_polygon_ids: set[int], max_body_offset: float):
    mesh = body.data
    mesh.calc_loop_triangles()
    body_world = body.matrix_world.copy()
    garment_world = garment.matrix_world.copy()
    world_vertices = [body_world @ vertex.co for vertex in mesh.vertices]
    selected_triangles = [triangle for triangle in mesh.loop_triangles
                          if triangle.polygon_index in allowed_polygon_ids]
    if not selected_triangles:
        raise RuntimeError("The declared body regions contain no triangulated surface.")
    triangles = [tuple(triangle.vertices) for triangle in selected_triangles]
    tree = BVHTree.FromPolygons(world_vertices, triangles, all_triangles=True)
    correspondences = []
    distances = []
    signed_offsets = []
    for vertex in garment.data.vertices:
        world_point = garment_world @ vertex.co
        nearest = tree.find_nearest(world_point)
        if nearest is None:
            raise RuntimeError(f"Could not map garment vertex {vertex.index} to the body surface")
        surface_point, surface_normal, triangle_index, distance = nearest
        if distance > max_body_offset:
            raise RuntimeError(
                f"Garment vertex {vertex.index} is {distance:.3f} m from its declared body regions "
                f"(limit {max_body_offset:.3f} m). Check the region declaration and garment fit."
            )
        distances.append(distance)
        signed_offset = (world_point - surface_point).dot(surface_normal)
        if signed_offset < -0.003:
            raise RuntimeError(
                f"Garment vertex {vertex.index} penetrates its declared body region by "
                f"{-signed_offset:.3f} m. Correct the fit before weight transfer."
            )
        signed_offsets.append(signed_offset)
        indices = triangles[triangle_index]
        weights = barycentric(surface_point, *(world_vertices[index] for index in indices))
        correspondences.append((indices, weights))
    return correspondences, world_vertices, distances, signed_offsets


def transfer_vertex_groups(
    garment: bpy.types.Object,
    body: bpy.types.Object,
    correspondences,
    max_influences: int,
    excluded: set[str],
) -> int:
    while garment.vertex_groups:
        garment.vertex_groups.remove(garment.vertex_groups[0])
    body_groups = {group.index: group for group in body.vertex_groups if group.name not in excluded}
    garment_groups = {group.name: garment.vertex_groups.new(name=group.name) for group in body_groups.values()}
    source_weights = [
        {entry.group: entry.weight for entry in vertex.groups}
        for vertex in body.data.vertices
    ]
    zero_weight_vertices = 0
    for vertex, (indices, bary) in zip(garment.data.vertices, correspondences):
        combined: dict[int, float] = {}
        for source_index, factor in zip(indices, bary):
            for group_index, weight in source_weights[source_index].items():
                if group_index in body_groups:
                    combined[group_index] = combined.get(group_index, 0.0) + weight * factor
        strongest = sorted(combined.items(), key=lambda item: item[1], reverse=True)[:max_influences]
        total = sum(weight for _, weight in strongest)
        if total <= 1e-10:
            zero_weight_vertices += 1
            continue
        for group_index, weight in strongest:
            group = body_groups[group_index]
            garment_groups[group.name].add([vertex.index], weight / total, "REPLACE")
    if zero_weight_vertices:
        raise RuntimeError(
            f"{zero_weight_vertices} garment vertices have no usable body weights. "
            "Remove excluded bones or move the garment closer to the body."
        )
    return zero_weight_vertices


def transfer_shape_keys(
    garment: bpy.types.Object,
    body: bpy.types.Object,
    correspondences,
) -> list[str]:
    if not body.data.shape_keys:
        return []
    body_keys = body.data.shape_keys.key_blocks
    basis = body_keys.get("Basis")
    if basis is None:
        raise RuntimeError("Atlas body has no Basis shape key")
    garment_basis = garment.shape_key_add(name="Basis", from_mix=False)
    garment_world = garment.matrix_world.copy()
    inverse_linear = garment_world.to_3x3().inverted()
    copied = []
    for source_key in body_keys:
        if source_key == basis:
            continue
        target = garment.shape_key_add(name=source_key.name, from_mix=False)
        target.relative_key = garment_basis
        for vertex, (indices, bary) in zip(garment.data.vertices, correspondences):
            world_delta = Vector((0.0, 0.0, 0.0))
            for source_index, factor in zip(indices, bary):
                delta_local = source_key.data[source_index].co - basis.data[source_index].co
                world_delta += (body.matrix_world.to_3x3() @ delta_local) * factor
            target.data[vertex.index].co = vertex.co + inverse_linear @ world_delta
        copied.append(source_key.name)
    return copied


def attach_to_rig(garment: bpy.types.Object, rig: bpy.types.Object) -> None:
    world_matrix = garment.matrix_world.copy()
    garment.parent = rig
    garment.matrix_parent_inverse = rig.matrix_world.inverted()
    garment.matrix_world = world_matrix
    for modifier in list(garment.modifiers):
        if modifier.type == "ARMATURE":
            garment.modifiers.remove(modifier)
    modifier = garment.modifiers.new("ATLAS_HUMANOID_V1 skin", "ARMATURE")
    modifier.object = rig
    modifier.use_vertex_groups = True


def export_asset(garment: bpy.types.Object, rig: bpy.types.Object, output: Path) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    garment.select_set(True)
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.export_scene.gltf(
        filepath=str(output),
        export_format="GLB",
        use_selection=True,
        export_skins=True,
        export_animations=False,
        export_apply=False,
        export_materials="EXPORT",
        export_cameras=False,
        export_lights=False,
        export_yup=True,
        export_extras=True,
    )


def main() -> None:
    args = arguments()
    source = args.blend.resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Working Blender file not found: {source}")
    bpy.ops.wm.open_mainfile(filepath=str(source))

    body = bpy.data.objects.get(args.body)
    rig = bpy.data.objects.get(args.rig)
    garment = bpy.data.objects.get(args.garment)
    if not body or body.type != "MESH":
        raise RuntimeError(f"Working file must contain body mesh {args.body}")
    if not rig or rig.type != "ARMATURE":
        raise RuntimeError(f"Working file must contain armature {args.rig}")
    if not garment or garment.type != "MESH" or garment == body:
        raise RuntimeError(f"Garment must be a separate mesh object named {args.garment}")
    if args.slot not in EQUIPMENT_SLOTS:
        raise ValueError(f"Unsupported equipment slot {args.slot!r}; choose one of {sorted(EQUIPMENT_SLOTS)}")
    if not set(args.region).issubset(SLOT_REGIONS[args.slot]):
        raise ValueError(f"Regions {sorted(set(args.region) - SLOT_REGIONS[args.slot])} are not valid for slot {args.slot!r}")
    if args.max_body_offset <= 0 or args.max_body_offset > 0.5:
        raise ValueError("--max-body-offset must be greater than 0 and no more than 0.5 meters")
    rig_contract = json.loads((ROOT / "art/characters/atlas_humanoid_v1/atlas_humanoid_v1.json").read_text())
    atlas_parents = {bone["name"]: bone["parent"] for bone in rig_contract["bones"]}
    rig_bones = {bone.name for bone in rig.data.bones}
    if rig_bones != set(atlas_parents):
        missing = sorted(set(atlas_parents) - rig_bones)
        extra = sorted(rig_bones - set(atlas_parents))
        raise RuntimeError(f"Rig does not match ATLAS_HUMANOID_V1; missing={missing}, extra={extra}")
    hierarchy_errors = [
        bone.name
        for bone in rig.data.bones
        if (bone.parent.name if bone.parent else None) != atlas_parents[bone.name]
    ]
    if hierarchy_errors:
        raise RuntimeError(f"Rig hierarchy does not match ATLAS_HUMANOID_V1 at: {hierarchy_errors}")
    if REGION_SCHEMA.get("skeleton_id") != "ATLAS_HUMANOID_V1":
        raise RuntimeError("Body-region schema does not target ATLAS_HUMANOID_V1")
    if REGION_SCHEMA.get("source_sha256") != rig_contract.get("source_sha256"):
        raise RuntimeError("Body-region schema is stale; rebuild it from the current base model")
    if not re.fullmatch(r"[a-zA-Z0-9_.-]+", args.asset_id):
        raise ValueError("Asset IDs may contain only letters, digits, dot, underscore, and hyphen")

    # Do not overwrite the artist's working file. All destructive operations
    # happen after loading it and are saved only to the output directory.
    args.output_dir.mkdir(parents=True, exist_ok=True)
    apply_authoring_modifiers(garment)
    allowed_polygon_ids = {
        polygon_index
        for region in set(args.region)
        for polygon_index in REGION_SCHEMA["regions"][region]["polygon_indices"]
    }
    correspondences, _, distances, signed_offsets = body_surface_map(
        body, garment, allowed_polygon_ids, args.max_body_offset)
    transfer_vertex_groups(garment, body, correspondences, args.max_influences, set(args.exclude_bone))
    shape_keys = transfer_shape_keys(garment, body, correspondences)
    attach_to_rig(garment, rig)

    garment["atlas.asset_id"] = args.asset_id
    garment["atlas.equipment_slot"] = args.slot
    garment["atlas.skeleton_version"] = "ATLAS_HUMANOID_V1"
    garment["atlas.morph_targets"] = ",".join(shape_keys)
    slug = re.sub(r"[^a-zA-Z0-9_.-]+", "_", args.asset_id)
    glb_path = args.output_dir / f"{slug}.glb"
    blend_path = args.output_dir / f"{slug}.blend"
    metadata_path = args.output_dir / f"{slug}.json"
    export_asset(garment, rig, glb_path)
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))

    metadata = {
        "schema": "atlas-equipment/v1",
        "asset_id": args.asset_id,
        "equipment_slot": args.slot,
        "body_regions": sorted(set(args.region)),
        "body_region_schema": "atlas-body-regions/v1",
        "body_region_source_sha256": REGION_SCHEMA["source_sha256"],
        "skeleton_id": "ATLAS_HUMANOID_V1",
        "body_object": body.name,
        "rig_object": rig.name,
        "source_blend": str(source),
        "runtime_glb": glb_path.name,
        "runtime_sha256": hashlib.sha256(glb_path.read_bytes()).hexdigest(),
        "mesh_object": garment.name,
        "vertex_count": len(garment.data.vertices),
        "body_morph_targets": shape_keys,
        "excluded_bone_groups": args.exclude_bone,
        "maximum_skin_influences": args.max_influences,
        "fit_review_required": True,
        "fit_review_status": "review_required",
        "body_surface_offset_m": {"mean": sum(distances) / len(distances), "maximum": max(distances)},
        "body_surface_signed_offset_m": {"minimum": min(signed_offsets), "maximum": max(signed_offsets)},
        "redistribution_status": "review_required",
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"Prepared equipment GLB: {glb_path}")
    print(f"Prepared Blender copy: {blend_path}")
    print(f"Equipment metadata: {metadata_path}")
    print("Preview every body morph and movement pose before registering this garment for players.")


if __name__ == "__main__":
    raise SystemExit("Paused: this workflow requires a newly reviewed base and rig. See tools/characters/README.md.")
