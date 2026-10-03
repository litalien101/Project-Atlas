"""RETIRED: depends on the removed female-base runtime GLB.

See tools/characters/README.md. This script is retained for historical review
and refuses direct execution.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "web/assets/characters/female_base_atlas_v1.glb"
OUTPUT_DIR = ROOT / "art/characters/atlas_humanoid_v1"
BLEND_OUTPUT = OUTPUT_DIR / "atlas_humanoid_v1.blend"
SPEC_OUTPUT = OUTPUT_DIR / "atlas_humanoid_v1.json"

SOCKETS = {
    "head": [("head", "mixamorig:Head")],
    "hair": [("hair", "mixamorig:Head")],
    "face": [("face", "mixamorig:Head")],
    "neck": [("neck", "mixamorig:Neck")],
    "shoulders": [
        ("shoulders_l", "mixamorig:LeftShoulder"),
        ("shoulders_r", "mixamorig:RightShoulder"),
    ],
    "cape": [("cape", "mixamorig:Spine2")],
    "chest": [("chest", "mixamorig:Spine2")],
    "gloves": [
        ("gloves_l", "mixamorig:LeftHand"),
        ("gloves_r", "mixamorig:RightHand"),
    ],
    "belt": [("belt", "mixamorig:Hips")],
    "legs": [("legs", "mixamorig:Hips")],
    "boots": [
        ("boots_l", "mixamorig:LeftFoot"),
        ("boots_r", "mixamorig:RightFoot"),
    ],
    "main_hand": [("main_hand", "mixamorig:RightHand")],
    "off_hand": [("off_hand", "mixamorig:LeftHand")],
    "back": [("back", "mixamorig:Spine2")],
}


def reset_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for collection in list(bpy.data.collections):
        if collection.name != bpy.context.scene.collection.name:
            bpy.data.collections.remove(collection)


def import_reference() -> tuple[bpy.types.Object, list[bpy.types.Object]]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"Mixamo reference model not found: {SOURCE}")
    bpy.ops.import_scene.gltf(filepath=str(SOURCE))
    imported = list(bpy.context.selected_objects)
    armatures = [obj for obj in imported if obj.type == "ARMATURE"]
    if len(armatures) != 1:
        raise RuntimeError(f"Expected one imported armature, found {len(armatures)}")
    armature = armatures[0]
    meshes = [obj for obj in imported if obj.type == "MESH"]
    if not meshes:
        raise RuntimeError("The reference model did not import any skinned meshes.")
    imported_set = set(imported)
    for obj in list(bpy.data.objects):
        if obj not in imported_set:
            bpy.data.objects.remove(obj, do_unlink=True)
    armature.name = "ATLAS_HUMANOID_V1_RIG"
    armature.data.name = "ATLAS_HUMANOID_V1"
    armature.show_in_front = True
    armature.data.display_type = "STICK"
    armature["atlas.skeleton_version"] = "ATLAS_HUMANOID_V1"
    armature["atlas.source"] = "web/assets/characters/female_base_atlas_v1.glb"
    armature["atlas.animation_contract"] = "Existing Mixamo-compatible locomotion set"
    for mesh in meshes:
        mesh["atlas.template_role"] = "reference_mesh_duplicate_before_editing"
    return armature, imported


def add_sockets(armature: bpy.types.Object) -> list[dict[str, str]]:
    collection = bpy.data.collections.new("ATLAS_HUMANOID_V1 · Equipment Sockets")
    bpy.context.scene.collection.children.link(collection)
    available_bones = set(armature.data.bones.keys())
    socket_records: list[dict[str, str]] = []
    for slot, entries in SOCKETS.items():
        for suffix, bone_name in entries:
            if bone_name not in available_bones:
                raise RuntimeError(f"Socket {suffix} refers to missing bone {bone_name}")
            pose_bone = armature.pose.bones[bone_name]
            socket = bpy.data.objects.new(f"SOCKET_{suffix}", None)
            collection.objects.link(socket)
            socket.empty_display_type = "SPHERE"
            socket.empty_display_size = 0.045
            socket.show_in_front = True
            socket.parent = armature
            socket.parent_type = "BONE"
            socket.parent_bone = bone_name
            # The imported Mixamo armature includes a 0.01 pose-space scale.
            # Use the evaluated pose matrix so markers align with the rendered mesh.
            socket.matrix_world = armature.matrix_world @ pose_bone.matrix
            socket["atlas.slot"] = slot
            socket["atlas.skeleton_version"] = "ATLAS_HUMANOID_V1"
            socket_records.append({"name": socket.name, "slot": slot, "bone": bone_name})
    return socket_records


def bone_manifest(armature: bpy.types.Object) -> list[dict[str, object]]:
    result = []
    for bone in armature.data.bones:
        result.append({
            "name": bone.name,
            "parent": bone.parent.name if bone.parent else None,
            "rest_matrix_armature_space": [
                [round(float(value), 8) for value in row] for row in bone.matrix_local
            ],
            "use_deform": bool(bone.use_deform),
        })
    return result


def reference_height(meshes: list[bpy.types.Object]) -> float:
    points = [
        mesh.matrix_world @ Vector(corner)
        for mesh in meshes
        for corner in mesh.bound_box
    ]
    return max(point.z for point in points) - min(point.z for point in points)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    reset_scene()
    armature, imported = import_reference()
    meshes = [obj for obj in imported if obj.type == "MESH"]
    sockets = add_sockets(armature)
    bpy.context.scene["atlas.skeleton_version"] = "ATLAS_HUMANOID_V1"
    bpy.context.scene["atlas.template_note"] = (
        "Rig and socket reference only. Preserve bone names and rest pose; "
        "duplicate the reference mesh before creating a new body or equipment."
    )
    bpy.ops.file.pack_all()

    manifest = {
        "schema": "atlas-humanoid-rig/v1",
        "skeleton_id": "ATLAS_HUMANOID_V1",
        "blender_version": bpy.app.version_string,
        "source_model": "web/assets/characters/female_base_atlas_v1.glb",
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "rig_object": armature.name,
        "bone_count": len(armature.data.bones),
        "bones": bone_manifest(armature),
        "sockets": sockets,
        "mesh_objects": [obj.name for obj in meshes],
        "source_height_blender_units": round(reference_height(meshes), 8),
        "coordinate_system": {
            "authoring_scale": "Preserve the source GLB scale and fit equipment to this reference.",
            "runtime_target_height_m": 1.68,
            "up_axis": "Z in Blender; the browser normalizes model height and glTF handles Y-up conversion",
            "forward_axis": "Preserve the reference model's authored orientation",
        },
        "animation_policy": (
            "Use the existing Mixamo-compatible Atlas clips. Do not edit animation "
            "timing, root motion, or the character controller in equipment work."
        ),
    }
    SPEC_OUTPUT.write_text(json.dumps(manifest, indent=2) + "\n")
    bpy.context.preferences.filepaths.save_version = 0
    BLEND_OUTPUT.with_suffix(BLEND_OUTPUT.suffix + "1").unlink(missing_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_OUTPUT))
    print(f"Created {BLEND_OUTPUT}")
    print(f"Created {SPEC_OUTPUT} ({manifest['bone_count']} bones, {len(sockets)} sockets)")


if __name__ == "__main__":
    raise SystemExit("Retired: required source asset was removed. See tools/characters/README.md.")
