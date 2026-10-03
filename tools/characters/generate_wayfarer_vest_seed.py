"""Generate a torso and shoulder vest seed for artist shaping and pipeline review.

This creates a fitted surface starting point. It is not a finished outfit and
is deliberately written to the workspaces directory, never to runtime assets.
"""

from __future__ import annotations

import bpy
import json
from pathlib import Path
from mathutils.bvhtree import BVHTree


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "art/characters/atlas_female_base_v1/atlas_female_base_v1.blend"
REGIONS = ROOT / "art/characters/atlas_female_base_v1/atlas_body_regions_v1.json"
OUTPUT = ROOT / "art/characters/workspaces/wayfarer_vest_region_seed.blend"
BODY_NAME = "ATLAS_FEMALE_BODY_V1"
GARMENT_NAME = "wayfarer_vest"
LOWER_HEM_Z = 1.025
# Derive the top edge from the rig's shoulder bones. Their inner ends mark the
# collarbone line; the small clearance keeps the vest just above that line.
COLLARBONE_CLEARANCE = 0.012
SHOULDER_MIN_Z = 1.300
SHOULDER_MAX_ABS_X = 0.205
SHOULDER_EDGE_CLEARANCE = 0.018
SURFACE_OFFSET = 0.012
RIG_NAME = "ATLAS_HUMANOID_V1_RIG"


def main() -> None:
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    body = bpy.data.objects.get(BODY_NAME)
    if body is None or body.type != "MESH":
        raise RuntimeError(f"Missing body mesh {BODY_NAME}")
    rig = bpy.data.objects.get(RIG_NAME)
    if rig is None or rig.type != "ARMATURE":
        raise RuntimeError(f"Missing rig {RIG_NAME}; collarbone placement requires shoulder landmarks")
    left_shoulder = rig.data.bones.get("mixamorig:LeftShoulder")
    right_shoulder = rig.data.bones.get("mixamorig:RightShoulder")
    if left_shoulder is None or right_shoulder is None:
        raise RuntimeError("Rig is missing left/right shoulder bones for collarbone placement")
    to_body_local = body.matrix_world.inverted() @ rig.matrix_world
    shoulder_heads = [to_body_local @ bone.head_local for bone in (left_shoulder, right_shoulder)]
    shoulder_tails = [to_body_local @ bone.tail_local for bone in (left_shoulder, right_shoulder)]
    inner_z = sum(point.z for point in shoulder_heads) / 2
    inner_abs_x = sum(abs(point.x) for point in shoulder_heads) / 2
    outer_z = sum(point.z for point in shoulder_tails) / 2
    outer_abs_x = sum(abs(point.x) for point in shoulder_tails) / 2
    collarbone_slope = (outer_z - inner_z) / max(outer_abs_x - inner_abs_x, 1e-6)

    def collarbone_top(abs_x: float) -> float:
        return inner_z + collarbone_slope * max(0.0, abs_x - inner_abs_x) + COLLARBONE_CLEARANCE
    region_schema = json.loads(REGIONS.read_text(encoding="utf-8"))
    expected_hash = json.loads((ROOT / "art/characters/atlas_female_base_v1/atlas_female_base_v1.json").read_text())["runtime_sha256"]
    if region_schema.get("schema") != "atlas-body-regions/v1" or region_schema.get("source_sha256") != expected_hash:
        raise RuntimeError("Body-region map is stale; rebuild it before generating a garment seed")
    torso_faces = set(region_schema["regions"]["torso"]["polygon_indices"])
    left_arm_faces = set(region_schema["regions"]["left_arm"]["polygon_indices"])
    right_arm_faces = set(region_schema["regions"]["right_arm"]["polygon_indices"])
    mesh = body.data
    mesh.update()
    selected_by_index = {}
    for polygon in mesh.polygons:
        z, x = polygon.center.z, polygon.center.x
        if polygon.index in torso_faces and LOWER_HEM_Z <= z <= collarbone_top(abs(x)):
            selected_by_index[polygon.index] = polygon
        elif (polygon.index in left_arm_faces | right_arm_faces
              and SHOULDER_MIN_Z <= z <= collarbone_top(abs(x)) + SHOULDER_EDGE_CLEARANCE
              and abs(x) <= SHOULDER_MAX_ABS_X):
            selected_by_index[polygon.index] = polygon
    selected_faces = list(selected_by_index.values())
    if len(selected_faces) < 200:
        raise RuntimeError(f"Torso region produced only {len(selected_faces)} faces; refusing the seed")

    used_vertices = {index for polygon in selected_faces for index in polygon.vertices}
    source_indices = sorted(used_vertices)
    index_map = {source: output for output, source in enumerate(source_indices)}
    faces = [tuple(index_map[index] for index in polygon.vertices) for polygon in selected_faces]
    mesh.calc_loop_triangles()
    selected_triangles = [triangle for triangle in mesh.loop_triangles
                          if triangle.polygon_index in selected_by_index]
    body_world = body.matrix_world.copy()
    world_vertices = [body_world @ vertex.co for vertex in mesh.vertices]
    triangles = [tuple(triangle.vertices) for triangle in selected_triangles]
    surface_tree = BVHTree.FromPolygons(world_vertices, triangles, all_triangles=True)
    inverse_body_world = body_world.inverted()
    coordinates = []
    for index in source_indices:
        world_point = body_world @ mesh.vertices[index].co
        nearest = surface_tree.find_nearest(world_point)
        if nearest is None:
            raise RuntimeError(f"Could not find an outward surface normal for body vertex {index}")
        _, surface_normal, _, _ = nearest
        offset_world = world_point + surface_normal.normalized() * SURFACE_OFFSET
        coordinates.append(inverse_body_world @ offset_world)

    # At the neck/arm transitions, two body regions can sit close together.
    # Push seam vertices away from the nearest allowed surface until they
    # have a small positive clearance; the preparation step still enforces
    # the hard penetration limit independently.
    for output_index, coordinate in enumerate(coordinates):
        world_point = body_world @ coordinate
        for _ in range(5):
            nearest = surface_tree.find_nearest(world_point)
            if nearest is None:
                raise RuntimeError(f"Could not validate surface clearance for garment vertex {output_index}")
            surface_point, surface_normal, _, _ = nearest
            signed_distance = (world_point - surface_point).dot(surface_normal)
            if signed_distance >= 0.008:
                break
            world_point += surface_normal.normalized() * (0.008 - signed_distance)
        coordinates[output_index] = inverse_body_world @ world_point

    garment_mesh = bpy.data.meshes.new("WAYFARER_VEST_REGION_SEED_MESH")
    garment_mesh.from_pydata(coordinates, [], faces)
    garment_mesh.update()
    garment = bpy.data.objects.new(GARMENT_NAME, garment_mesh)
    bpy.context.collection.objects.link(garment)
    garment.matrix_world = body.matrix_world.copy()
    for polygon in garment.data.polygons:
        polygon.use_smooth = True
    fabric = bpy.data.materials.new("Wayfarer · deep teal woven cloth")
    fabric.diffuse_color = (0.035, 0.19, 0.17, 1.0)
    fabric.use_nodes = True
    shader = fabric.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (0.035, 0.19, 0.17, 1.0)
    shader.inputs["Roughness"].default_value = 0.86
    garment.data.materials.append(fabric)
    solidify = garment.modifiers.new("Fabric thickness · pending review", "SOLIDIFY")
    solidify.thickness = 0.008
    solidify.offset = 1.0
    garment["atlas.asset_id"] = "atlas.clothing.wayfarer_vest_v1"
    garment["atlas.equipment_slot"] = "chest"
    garment["atlas.body_regions"] = "torso,left_arm,right_arm"
    garment["atlas.body_region_schema"] = "atlas-body-regions/v1"
    garment["atlas.fit_review_status"] = "review_required"
    garment["atlas.generator_note"] = (
        "Torso/proximal-shoulder surface seed; upper edge follows rig shoulder landmarks. "
        "Head faces are excluded so the vest cannot extend onto the face. "
        "Shape, hem, armholes, and clipping require artist review."
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT))
    print(f"Generated pending vest seed: {OUTPUT}")
    print(f"Source regions: torso and proximal shoulders; faces: {len(selected_faces)}; vertices: {len(source_indices)}")
    print(f"Hem: Z={LOWER_HEM_Z:.3f} m; rig collarbone center: Z={inner_z:.3f} m; top clearance: {COLLARBONE_CLEARANCE:.3f} m")


if __name__ == "__main__":
    main()
