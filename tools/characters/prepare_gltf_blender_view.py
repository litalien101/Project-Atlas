"""Create a Blender inspection file from a GLB without rig-through-mesh overlays.

Run with:
  blender --background --python tools/characters/prepare_gltf_blender_view.py -- \
    --input path/to/character.glb
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    args.input = args.input.expanduser().resolve()
    if args.output is None:
        args.output = args.input.with_name(f"{args.input.stem}_blender_view.blend")
    else:
        args.output = args.output.expanduser().resolve()
    if not args.input.is_file() or args.input.suffix.lower() != ".glb":
        raise ValueError("--input must be an existing .glb file")
    return args


def prepare_view(input_path: Path, output_path: Path) -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=str(input_path))

    armatures = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    for armature in armatures:
        # GLB has no Blender viewport display flag; Blender's importer defaults
        # imported armatures to drawing in front of the skinned mesh. Keep the
        # rig available in the Outliner, but hide its bone display in this
        # inspection file so it cannot read as black fragments through skin or
        # clothing. The armature and skinning remain in the GLB itself.
        armature.show_in_front = False
        armature.hide_set(True)

    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if not meshes:
        raise RuntimeError(f"GLB contains no mesh objects: {input_path}")
    world_bounds = [obj.matrix_world @ Vector(point) for obj in meshes for point in obj.bound_box]
    low = Vector(tuple(min(point[i] for point in world_bounds) for i in range(3)))
    high = Vector(tuple(max(point[i] for point in world_bounds) for i in range(3)))
    center = (low + high) * 0.5
    height = max(high.z - low.z, 0.1)

    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = None
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type != "VIEW_3D":
                continue
            space = area.spaces.active
            space.region_3d.view_location = center
            # Imported MakeHuman characters face toward negative Y.
            space.region_3d.view_rotation = Vector((0, 1, 0)).to_track_quat("-Z", "Y")
            space.region_3d.view_distance = max(height * 2.8, 2.5)
            space.region_3d.view_perspective = "ORTHO"
            space.shading.type = "MATERIAL"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(output_path))
    manifest_path = input_path.with_name("build.json")
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest.setdefault("outputs", {})["blender_view"] = {
            "path": output_path.name,
            "sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
        }
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"GLB_BLENDER_VIEW_OK {output_path} armatures={len(armatures)} in_front=false")


if __name__ == "__main__":
    arguments = parse_args()
    prepare_view(arguments.input, arguments.output)
