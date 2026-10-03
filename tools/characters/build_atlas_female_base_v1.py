"""RETIRED: depends on removed, rights-unverified female base/underwear sources.

See tools/characters/README.md. This script is retained for historical review
and refuses direct execution.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "art/characters/atlas_female_base_v1"
SOURCE_COPY = OUTPUT_DIR / "female_base_source.blend"
SOURCE = SOURCE_COPY
UNDERWEAR_ARCHIVE = OUTPUT_DIR / "underwear_source/underwear.zip"
UNDERWEAR_SOURCE = OUTPUT_DIR / "underwear_source"
BLEND_OUTPUT = OUTPUT_DIR / "atlas_female_base_v1.blend"
GLB_OUTPUT = ROOT / "web/assets/characters/female_base_atlas_v1.glb"
MANIFEST_OUTPUT = OUTPUT_DIR / "atlas_female_base_v1.json"

BODY_NAME = "ATLAS_FEMALE_BODY_V1"
RIG_NAME = "ATLAS_HUMANOID_V1_RIG"
RUNTIME_TEXTURES = UNDERWEAR_SOURCE / "runtime_textures"

EXPECTED_BONES = {
    "mixamorig:LeftEye",
    "mixamorig:RightEye",
}


def find_source_objects() -> tuple[bpy.types.Object, bpy.types.Object]:
    armatures = [obj for obj in bpy.data.objects if obj.type == "ARMATURE"]
    meshes = [obj for obj in bpy.data.objects if obj.type == "MESH" and len(obj.data.vertices) > 1000]
    if len(armatures) != 1 or len(meshes) != 1:
        raise RuntimeError(
            f"Expected one armature and one skinned body mesh; found {len(armatures)} and {len(meshes)}."
        )
    return armatures[0], meshes[0]


def make_material(name: str, color: tuple[float, float, float], roughness: float) -> bpy.types.Material:
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    material.diffuse_color = (*color, 1.0)
    material.use_nodes = True
    shader = material.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color, 1.0)
    shader.inputs["Roughness"].default_value = roughness
    return material


def add_standard_eye_bones(armature: bpy.types.Object) -> None:
    missing = EXPECTED_BONES - set(armature.data.bones.keys())
    if not missing:
        return
    if missing != EXPECTED_BONES:
        raise RuntimeError(f"Unexpected partial eye-bone set: {sorted(missing)}")
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode="EDIT")
    edit_bones = armature.data.edit_bones
    head = edit_bones.get("mixamorig:Head")
    if head is None:
        raise RuntimeError("The source armature is missing mixamorig:Head")
    inverse_world = armature.matrix_world.inverted()
    for side, sign in (("Left", -1.0), ("Right", 1.0)):
        eye = edit_bones.new(f"mixamorig:{side}Eye")
        eye.head = inverse_world @ Vector((sign * 0.025, 0.084, 1.566))
        eye.tail = inverse_world @ Vector((sign * 0.025, 0.11, 1.566))
        eye.parent = head
        eye.use_deform = True
    bpy.ops.object.mode_set(mode="OBJECT")


def assign_skin_material(body: bpy.types.Object) -> None:
    skin = make_material("Atlas · warm skin", (0.47, 0.27, 0.18), 0.78)
    body.data.materials.clear()
    body.data.materials.append(skin)
    for polygon in body.data.polygons:
        polygon.material_index = 0


def extract_underwear_archive() -> Path:
    if not UNDERWEAR_ARCHIVE.is_file():
        raise FileNotFoundError(f"Underwear archive not found: {UNDERWEAR_ARCHIVE}")
    UNDERWEAR_SOURCE.mkdir(parents=True, exist_ok=True)
    shutil.copy2(UNDERWEAR_ARCHIVE, UNDERWEAR_SOURCE / UNDERWEAR_ARCHIVE.name)
    with zipfile.ZipFile(UNDERWEAR_ARCHIVE) as archive:
        for entry in archive.infolist():
            target = (UNDERWEAR_SOURCE / entry.filename).resolve()
            if not target.is_relative_to(UNDERWEAR_SOURCE.resolve()):
                raise RuntimeError(f"Unsafe path in underwear archive: {entry.filename}")
        archive.extractall(UNDERWEAR_SOURCE)
    return UNDERWEAR_SOURCE / "source/under.fbx"


def material_from_maps(name: str, archive_prefix: str) -> bpy.types.Material:
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    material.surface_render_method = "DITHERED"
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    shader = nodes.get("Principled BSDF")
    shader.inputs["Roughness"].default_value = 0.72

    def load_map(filename: str, color_space: str) -> np.ndarray | None:
        source_path = UNDERWEAR_SOURCE / "textures" / f"{archive_prefix}_{filename}.png"
        if not source_path.is_file():
            return None
        image = bpy.data.images.load(str(source_path), check_existing=True)
        image.colorspace_settings.name = color_space
        if max(image.size) > 1024:
            image.scale(1024, 1024)
        pixels = np.asarray(image.pixels[:], dtype=np.float32).reshape(image.size[1], image.size[0], 4).copy()
        bpy.data.images.remove(image)
        return pixels

    def packed_image_node(image_name: str, pixels: np.ndarray, color_space: str) -> bpy.types.Node:
        RUNTIME_TEXTURES.mkdir(parents=True, exist_ok=True)
        image = bpy.data.images.new(image_name, width=pixels.shape[1], height=pixels.shape[0], alpha=True)
        image.colorspace_settings.name = color_space
        image.pixels.foreach_set(np.clip(pixels, 0.0, 1.0).astype(np.float32, copy=False).ravel())
        image.filepath_raw = str(RUNTIME_TEXTURES / f"{image_name}.png")
        image.file_format = "PNG"
        image.save()
        image.pack()
        node = nodes.new("ShaderNodeTexImage")
        node.image = image
        node.label = image_name.replace("_", " ").title()
        return node

    base_color = load_map("Base_Color", "sRGB")
    opacity = load_map("Opacity", "Non-Color")
    if base_color is not None:
        if opacity is not None:
            base_color[:, :, 3] = opacity[:, :, 0]
        base = packed_image_node(f"{archive_prefix}_BaseColor", base_color, "sRGB")
        links.new(base.outputs["Color"], shader.inputs["Base Color"])
        if opacity is not None:
            links.new(base.outputs["Alpha"], shader.inputs["Alpha"])

    roughness = load_map("Roughness", "Non-Color")
    metallic = load_map("Metallic", "Non-Color")
    if roughness is not None or metallic is not None:
        shape = (1024, 1024, 4)
        packed = np.zeros(shape, dtype=np.float32)
        packed[:, :, 1] = roughness[:, :, 0] if roughness is not None else 0.72
        packed[:, :, 2] = metallic[:, :, 0] if metallic is not None else 0.0
        packed[:, :, 3] = 1.0
        orm = packed_image_node(f"{archive_prefix}_MetallicRoughness", packed, "Non-Color")
        separate = nodes.new("ShaderNodeSeparateColor")
        links.new(orm.outputs["Color"], separate.inputs["Color"])
        links.new(separate.outputs["Green"], shader.inputs["Roughness"])
        links.new(separate.outputs["Blue"], shader.inputs["Metallic"])

    normal = load_map("Normal", "Non-Color")
    if normal is not None:
        normal_node = packed_image_node(f"{archive_prefix}_Normal", normal, "Non-Color")
        normal_node.image.colorspace_settings.name = "Non-Color"
        map_node = nodes.new("ShaderNodeNormalMap")
        links.new(normal_node.outputs["Color"], map_node.inputs["Color"])
        links.new(map_node.outputs["Normal"], shader.inputs["Normal"])
    # Height is omitted from the runtime material; the supplied map is retained
    # in the authoring source, while glTF has no portable height input.
    material.diffuse_color = (0.24, 0.17, 0.20, 1.0)
    return material


def import_and_skin_underwear(armature: bpy.types.Object, body: bpy.types.Object) -> list[bpy.types.Object]:
    fbx_path = extract_underwear_archive()
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=str(fbx_path), use_image_search=False)
    imported = [obj for obj in bpy.data.objects if obj not in before]
    garments = [obj for obj in imported if obj.type == "MESH" and len(obj.data.vertices) > 100]
    for obj in imported:
        if obj not in garments:
            bpy.data.objects.remove(obj, do_unlink=True)
    if len(garments) != 2:
        raise RuntimeError(f"Expected bra and briefs meshes in underwear FBX; found {len(garments)}.")

    garment_materials = {
        "RetopoFlow": material_from_maps("Atlas · underwear top", "up"),
        "RetopoFlow.001": material_from_maps("Atlas · underwear bottom", "bottom"),
    }
    for garment in garments:
        garment.name = "ATLAS_UNDERWEAR_BRA_V1" if garment.name == "RetopoFlow" else "ATLAS_UNDERWEAR_BRIEFS_V1"
        garment.data.name = garment.name + "_MESH"
        garment.data.materials.clear()
        prefix = "top" if garment.name.endswith("BRA_V1") else "bottom"
        garment.data.materials.append(garment_materials["RetopoFlow" if prefix == "top" else "RetopoFlow.001"])
        garment.parent = None
        garment.matrix_parent_inverse.identity()
        garment.matrix_world = garment.matrix_world.copy()

        # The supplied bra FBX faces the opposite way from the Mixamo body.
        # Turn it 180 degrees around the upright axis before conforming it.
        if garment.name.endswith("BRA_V1"):
            world_matrix = garment.matrix_world.copy()
            inverse_world = world_matrix.inverted()
            for vertex in garment.data.vertices:
                world = world_matrix @ vertex.co
                world.x = -world.x
                world.y = -world.y
                vertex.co = inverse_world @ world
            garment.data.update()

        # The supplied garment is close in the rest pose but was not authored
        # for this exact body. Conform its surface once, then skin it to the rig.
        shrink = garment.modifiers.new("Atlas fit to female base", "SHRINKWRAP")
        shrink.target = body
        shrink.wrap_method = "NEAREST_SURFACEPOINT"
        shrink.offset = 0.006
        bpy.context.view_layer.objects.active = garment
        garment.select_set(True)
        bpy.ops.object.modifier_apply(modifier=shrink.name)
        garment.select_set(False)
        excluded_groups = {"mixamorig:Head", "mixamorig:Neck", "mixamorig:LeftEye", "mixamorig:RightEye"} if garment.name.endswith("BRA_V1") else set()
        transfer_vertex_weights(garment, body, excluded_groups=excluded_groups)
        add_body_build_shapes(garment)
        arm_mod = garment.modifiers.new("ATLAS_HUMANOID_V1 skin", "ARMATURE")
        arm_mod.object = armature
        arm_mod.use_vertex_groups = True
        world_matrix = garment.matrix_world.copy()
        garment.parent = armature
        garment.matrix_parent_inverse = armature.matrix_world.inverted()
        garment.matrix_world = world_matrix
        garment["atlas.skeleton_version"] = "ATLAS_HUMANOID_V1"
        garment["atlas.template_role"] = "removable underwear equipment"
        garment["atlas.equipment_slot"] = "underwear_top" if garment.name.endswith("BRA_V1") else "underwear_bottom"
        garment["atlas.asset_id"] = "atlas.underwear.bra_v1" if garment.name.endswith("BRA_V1") else "atlas.underwear.briefs_v1"
    return garments


def transfer_vertex_weights(
    garment: bpy.types.Object,
    body: bpy.types.Object,
    excluded_groups: set[str] | None = None,
) -> None:
    mesh = body.data
    mesh.calc_loop_triangles()
    world_vertices = [body.matrix_world @ vertex.co for vertex in mesh.vertices]
    triangles = [tuple(tri.vertices) for tri in mesh.loop_triangles]
    tree = BVHTree.FromPolygons(world_vertices, triangles, all_triangles=True)
    group_by_name = {group.name: group for group in body.vertex_groups}
    garment_groups = {name: garment.vertex_groups.new(name=name) for name in group_by_name}
    weights_by_vertex = []
    for vertex in mesh.vertices:
        weights_by_vertex.append({entry.group: entry.weight for entry in vertex.groups})

    for vertex in garment.data.vertices:
        world_point = garment.matrix_world @ vertex.co
        nearest = tree.find_nearest(world_point)
        if nearest is None:
            continue
        point, _normal, triangle_index, _distance = nearest
        a_idx, b_idx, c_idx = triangles[triangle_index]
        a, b, c = (world_vertices[i] for i in (a_idx, b_idx, c_idx))
        v0, v1, v2 = b - a, c - a, point - a
        d00, d01, d11 = v0.dot(v0), v0.dot(v1), v1.dot(v1)
        d20, d21 = v2.dot(v0), v2.dot(v1)
        denom = d00 * d11 - d01 * d01
        if abs(denom) < 1e-12:
            bary = (1.0, 0.0, 0.0)
        else:
            v = (d11 * d20 - d01 * d21) / denom
            w = (d00 * d21 - d01 * d20) / denom
            bary = (max(0.0, 1.0 - v - w), max(0.0, v), max(0.0, w))
            total = sum(bary)
            bary = tuple(value / total for value in bary) if total else (1.0, 0.0, 0.0)
        combined: dict[int, float] = {}
        for source_index, factor in zip((a_idx, b_idx, c_idx), bary):
            for group_index, weight in weights_by_vertex[source_index].items():
                group_name = body.vertex_groups[group_index].name
                if group_name not in (excluded_groups or set()):
                    combined[group_index] = combined.get(group_index, 0.0) + weight * factor
        selected = sorted(combined.items(), key=lambda item: item[1], reverse=True)[:4]
        total = sum(weight for _, weight in selected)
        if total <= 0:
            # Upper bra straps can sit closest to the head in the source mesh.
            # Keep those vertices on the upper torso rather than letting them
            # follow head animation across the face.
            fallback = garment.vertex_groups.get("mixamorig:Spine2")
            if fallback is not None and excluded_groups:
                fallback.add([vertex.index], 1.0, "REPLACE")
            continue
        for group_index, weight in selected:
            group_name = body.vertex_groups[group_index].name
            garment_groups[group_name].add([vertex.index], weight / total, "REPLACE")


def add_body_build_shapes(obj: bpy.types.Object) -> None:
    """Add body-build and localized proportion targets to the body and wearables."""
    if obj.data.shape_keys is None:
        obj.shape_key_add(name="Basis", from_mix=False)
    basis = obj.data.shape_keys.key_blocks["Basis"]
    world_matrix = obj.matrix_world.copy()
    inverse_world = world_matrix.inverted()
    for name, direction in (("Build_Light", -1.0), ("Build_Heavy", 1.0)):
        key = obj.shape_key_add(name=name, from_mix=False)
        for base_point, key_point in zip(basis.data, key.data):
            world = world_matrix @ base_point.co
            torso = max(0.0, 1.0 - abs(world.z - 0.94) / 0.56)
            hip = max(0.0, 1.0 - abs(world.z - 0.87) / 0.26)
            width = 1.0 + direction * (0.11 * torso + 0.035 * hip)
            depth = 1.0 + direction * (0.075 * torso + 0.025 * hip)
            changed = Vector((world.x * width, world.y * depth, world.z))
            key_point.co = inverse_world @ changed

    def falloff(distance: float, radius: float) -> float:
        t = max(0.0, 1.0 - abs(distance) / radius)
        return t * t * (3.0 - 2.0 * t)

    def smooth_gate(value: float, radius: float) -> float:
        t = max(0.0, min(1.0, value / radius))
        return t * t * (3.0 - 2.0 * t)

    def make_target(name: str, deform) -> None:
        key = obj.shape_key_add(name=name, from_mix=False)
        for base_point, key_point in zip(basis.data, key.data):
            world = world_matrix @ base_point.co
            key_point.co = inverse_world @ deform(world)

    def bust(direction: float):
        def deform(point: Vector) -> Vector:
            x, y, z = point
            front = smooth_gate(y + 0.012, 0.055)
            influence = max(
                falloff(x - center, 0.082) * falloff(z - 1.205, 0.105)
                for center in (-0.078, 0.078)
            ) * front
            center_x = -0.078 if x < 0 else 0.078
            return Vector((
                center_x + (x - center_x) * (1.0 + 0.16 * direction * influence),
                y + 0.042 * direction * influence,
                1.205 + (z - 1.205) * (1.0 + 0.08 * direction * influence),
            ))
        return deform

    def stomach(direction: float):
        def deform(point: Vector) -> Vector:
            x, y, z = point
            influence = falloff(x, 0.235) * falloff(z - 0.99, 0.27) * smooth_gate(abs(y) - 0.004, 0.04)
            side = 1.0 if y >= 0 else -1.0
            return Vector((x, y + side * 0.05 * direction * influence, z))
        return deform

    def glutes(direction: float):
        def deform(point: Vector) -> Vector:
            x, y, z = point
            influence = falloff(x, 0.23) * falloff(z - 0.88, 0.25) * smooth_gate(-y - 0.005, 0.045)
            width = 1.0 + 0.06 * direction * influence
            return Vector((x * width, y - 0.055 * direction * influence, z))
        return deform

    def hips(direction: float):
        def deform(point: Vector) -> Vector:
            x, y, z = point
            influence = falloff(z - 0.88, 0.29) * falloff(x, 0.29)
            return Vector((x * (1.0 + 0.10 * direction * influence), y, z))
        return deform

    def thighs(direction: float):
        def deform(point: Vector) -> Vector:
            x, y, z = point
            influence = max(falloff(x - side * 0.16, 0.17) for side in (-1, 1)) * falloff(z - 0.62, 0.25)
            x_center = -0.16 if x < 0 else 0.16
            return Vector((x_center + (x - x_center) * (1.0 + 0.10 * direction * influence), y, z))
        return deform

    for smaller, larger, deform in (
        ("Bust_Smaller", "Bust_Larger", bust),
        ("Stomach_Flatter", "Stomach_Fuller", stomach),
        ("Glutes_Smaller", "Glutes_Larger", glutes),
        ("Hips_Narrower", "Hips_Wider", hips),
        ("Thighs_Slimmer", "Thighs_Fuller", thighs),
    ):
        make_target(smaller, deform(-1.0))
        make_target(larger, deform(1.0))


def enforce_glb_skin_weight_limit(body: bpy.types.Object, limit: int = 4) -> int:
    """Keep the strongest four influences per vertex and normalize them."""
    removals: dict[int, list[int]] = {}
    updates: list[tuple[int, list[tuple[int, float]]]] = []
    for vertex in body.data.vertices:
        memberships = sorted(vertex.groups, key=lambda entry: entry.weight, reverse=True)
        kept = memberships[:limit]
        if len(memberships) > limit:
            for entry in memberships[limit:]:
                removals.setdefault(entry.group, []).append(vertex.index)
        total = sum(entry.weight for entry in kept)
        if total > 0:
            updates.append((vertex.index, [(entry.group, entry.weight / total) for entry in kept]))
    for group_index, vertices in removals.items():
        body.vertex_groups[group_index].remove(vertices)
    for vertex_index, weights in updates:
        for group_index, weight in weights:
            body.vertex_groups[group_index].add([vertex_index], weight, "REPLACE")
    return sum(len(indices) for indices in removals.values())


def export_character(body: bpy.types.Object, armature: bpy.types.Object, garments: list[bpy.types.Object]) -> None:
    GLB_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    body.select_set(True)
    armature.select_set(True)
    for garment in garments:
        garment.select_set(True)
    bpy.context.view_layer.objects.active = armature
    bpy.ops.export_scene.gltf(
        filepath=str(GLB_OUTPUT),
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
    if not SOURCE.is_file():
        raise FileNotFoundError(f"Source Blender file not found: {SOURCE}")
    if not UNDERWEAR_ARCHIVE.is_file():
        raise FileNotFoundError(f"Underwear archive not found: {UNDERWEAR_ARCHIVE}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if SOURCE.resolve() != SOURCE_COPY.resolve():
        shutil.copy2(SOURCE, SOURCE_COPY)
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    armature, body = find_source_objects()

    armature.name = RIG_NAME
    armature.data.name = "ATLAS_HUMANOID_V1"
    armature["atlas.skeleton_version"] = "ATLAS_HUMANOID_V1"
    armature["atlas.source"] = "art/characters/atlas_female_base_v1/female_base_source.blend"
    armature["atlas.animation_contract"] = "Existing Mixamo-compatible locomotion set"
    body.name = BODY_NAME
    body["atlas.template_role"] = "bare female base body mesh"
    body["atlas.skeleton_version"] = "ATLAS_HUMANOID_V1"

    assign_skin_material(body)
    add_standard_eye_bones(armature)
    trimmed_weights = enforce_glb_skin_weight_limit(body)
    garments = import_and_skin_underwear(armature, body)
    add_body_build_shapes(body)

    # The source viewport camera and lights are useful in Blender but must not
    # become model nodes in the browser export.
    for obj in list(bpy.data.objects):
        if obj.type in {"CAMERA", "LIGHT"}:
            bpy.data.objects.remove(obj, do_unlink=True)

    bpy.context.scene["atlas.skeleton_version"] = "ATLAS_HUMANOID_V1"
    bpy.context.scene["atlas.character_id"] = "atlas.female_base_v1"
    bpy.context.scene["atlas.character_notes"] = (
        "Mixamo-compatible female body with the supplied bra and briefs as separate, rigged meshes."
    )

    bones = [
        {"name": bone.name, "parent": bone.parent.name if bone.parent else None}
        for bone in armature.data.bones
    ]
    bone_names = {bone["name"] for bone in bones}
    if len(bones) != 67 or not EXPECTED_BONES.issubset(bone_names):
        raise RuntimeError(f"Expected the 67-bone Atlas humanoid rig; found {len(bones)} bones.")

    export_character(body, armature, garments)
    bpy.context.preferences.filepaths.save_version = 0
    BLEND_OUTPUT.with_suffix(BLEND_OUTPUT.suffix + "1").unlink(missing_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_OUTPUT))

    source_hash = hashlib.sha256(SOURCE_COPY.read_bytes()).hexdigest()
    glb_hash = hashlib.sha256(GLB_OUTPUT.read_bytes()).hexdigest()
    manifest = {
        "schema": "atlas-character/v1",
        "asset_id": "atlas.female_base_v1",
        "skeleton_id": "ATLAS_HUMANOID_V1",
        "source_blend": "art/characters/atlas_female_base_v1/female_base_source.blend",
        "source_sha256": source_hash,
        "runtime_glb": "web/assets/characters/female_base_atlas_v1.glb",
        "runtime_sha256": glb_hash,
        "body_object": body.name,
        "mesh_vertices": len(body.data.vertices),
        "bone_count": len(bones),
        "bones": bones,
        "materials": sorted({
            material.name
            for obj in [body, *garments]
            for material in obj.data.materials
            if material
        }),
        "underwear_archive": "art/characters/atlas_female_base_v1/underwear_source/underwear.zip",
        "underwear_archive_sha256": hashlib.sha256(UNDERWEAR_ARCHIVE.read_bytes()).hexdigest(),
        "underwear_meshes": [
            {"object": garment.name, "vertices": len(garment.data.vertices), "polygons": len(garment.data.polygons)}
            for garment in garments
        ],
        "underwear_textures_max_dimension": 1024,
        "customization": {
            "skin_tone": "runtime material color",
            "height_m": {"minimum": 1.50, "maximum": 1.90, "method": "uniform character scale"},
            "weight_visual_range_kg": [45, 120],
            "body_build_shape_keys": ["Build_Light", "Build_Heavy"],
            "proportion_shape_keys": {
                "bust_percent": ["Bust_Smaller", "Bust_Larger"],
                "stomach_percent": ["Stomach_Flatter", "Stomach_Fuller"],
                "glutes_percent": ["Glutes_Smaller", "Glutes_Larger"],
                "hip_percent": ["Hips_Narrower", "Hips_Wider"],
                "thigh_percent": ["Thighs_Slimmer", "Thighs_Fuller"],
            },
            "body_mesh_has_baked_underwear": False,
            "underwear_equipment_slots": ["underwear_top", "underwear_bottom"],
        },
        "vertices_trimmed_to_glb_four_influence_limit": trimmed_weights,
        "body_height_m": round(float(body.dimensions.z), 6),
        "modifications": [
            "Added warm skin material.",
            "Kept underwear off the base body mesh and added the supplied bra and briefs as separate, conformed equipment meshes.",
            "Added matching Build_Light and Build_Heavy shape keys to the base body and underwear equipment.",
            "Connected the supplied base color, opacity, roughness, metallic, and normal maps; resized runtime textures to 1024 pixels maximum.",
            "Added non-destructive Mixamo LeftEye and RightEye bones to match the Atlas skeleton contract.",
        ],
        "animation_policy": "Use Atlas's existing Mixamo-compatible clips and runtime retargeter.",
    }
    MANIFEST_OUTPUT.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Created {BLEND_OUTPUT}")
    print(f"Created {GLB_OUTPUT}")
    print(f"Rigged underwear meshes: {[garment.name for garment in garments]}")
    print(f"Trimmed excess skin influences: {trimmed_weights}")
    print(f"Rig bones: {len(bones)}")


if __name__ == "__main__":
    raise SystemExit("Retired: required source assets were removed. See tools/characters/README.md.")
