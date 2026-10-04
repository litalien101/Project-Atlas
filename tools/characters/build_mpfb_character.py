"""Build a modular, recipe-driven MakeHuman/MPFB character in Blender.

Run with Blender 4.2+ and MPFB/system assets installed:
  blender --background --python tools/characters/build_mpfb_character.py -- \
    --recipe art/characters/profiles/mpfb_prototype.json

The recipe is deliberately a narrow proof of concept. It selects supported
MPFB macro controls and swappable system assets; it does not infer geometry
from free-form text.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[2]


def mpfb_symbol(module_suffix: str, symbol: str):
    for module_name in tuple(sys.modules):
        if module_name.endswith(module_suffix):
            module = importlib.import_module(module_name)
            if hasattr(module, symbol):
                return getattr(module, symbol)
    raise RuntimeError(
        f"MPFB module {module_suffix!r} is not loaded. Enable/install MPFB "
        "and its system assets in the Blender used for this build."
    )


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recipe", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    if not args.recipe.is_absolute():
        args.recipe = ROOT / args.recipe
    if args.output_dir is None:
        build_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        args.output_dir = ROOT / "art/characters/pending_models/mpfb_prototype" / build_id
    elif not args.output_dir.is_absolute():
        args.output_dir = ROOT / args.output_dir
    return args


def validate_recipe(recipe: dict) -> None:
    allowed = {"schema", "character_id", "macro", "skin", "hair", "shirt", "pants"}
    if set(recipe) - allowed:
        raise ValueError(f"Unsupported recipe keys: {sorted(set(recipe) - allowed)}")
    if recipe.get("schema") != "atlas-mpfb-character-recipe/v1":
        raise ValueError("Recipe schema must be atlas-mpfb-character-recipe/v1")
    character_id = recipe.get("character_id")
    if not isinstance(character_id, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,47}", character_id):
        raise ValueError("character_id must be a simple alphanumeric ID with optional underscores")
    macro = recipe.get("macro")
    if not isinstance(macro, dict) or set(macro) - {"gender", "age", "muscle", "weight", "proportions", "height", "cupsize", "firmness", "race"}:
        raise ValueError("macro must contain only supported MPFB macro controls")
    for name, value in macro.items():
        if name == "race":
            if not isinstance(value, dict) or set(value) != {"asian", "caucasian", "african"}:
                raise ValueError("race must set asian, caucasian, and african weights")
            if abs(sum(value.values()) - 1.0) > 1e-6:
                raise ValueError("race weights must sum to 1")
            values = value.values()
        else:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"macro.{name} must be a number from 0 to 1")
            values = (value,)
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 1 for v in values):
            raise ValueError(f"macro.{name} values must be between 0 and 1")
    for field in ("skin", "hair", "shirt", "pants"):
        value = recipe.get(field)
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", value):
            raise ValueError(f"{field} must be an asset name from its MPFB category")


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def build(recipe: dict, output_dir: Path) -> None:
    HumanService = mpfb_symbol("mpfb.services.humanservice", "HumanService")
    AssetService = mpfb_symbol("mpfb.services.assetservice", "AssetService")
    TargetService = mpfb_symbol("mpfb.services.targetservice", "TargetService")
    ObjectService = mpfb_symbol("mpfb.services.objectservice", "ObjectService")
    ExportService = mpfb_symbol("mpfb.services.exportservice", "ExportService")

    macro = TargetService.get_default_macro_info_dict()
    macro.update(recipe["macro"])
    clear_scene()
    body = HumanService.create_human(scale=0.1, feet_on_ground=True, macro_detail_dict=macro)

    skin_path = AssetService.find_asset_absolute_path(recipe["skin"] + ".mhmat", asset_subdir="skins")
    if not skin_path:
        raise RuntimeError(f"MPFB skin not found: {recipe['skin']}")
    HumanService.set_character_skin(skin_path, body, skin_type="GAMEENGINE")
    armature = HumanService.add_builtin_rig(body, "game_engine")
    for bone in armature.data.bones:
        if bone.name == "Root":
            bone.name = "root"
            break

    for subdir, filename, asset_type in (
        ("eyes", "low-poly.mhclo", "Eyes"),
        ("eyebrows", "eyebrow001.mhclo", "Eyebrows"),
        ("eyelashes", "eyelashes01.mhclo", "Eyelashes"),
        ("teeth", "teeth_base.mhclo", "Teeth"),
        ("hair", recipe["hair"] + ".mhclo", "Hair"),
        ("clothes", recipe["pants"] + ".mhclo", "Clothes"),
        ("clothes", recipe["shirt"] + ".mhclo", "Clothes"),
    ):
        path = AssetService.find_asset_absolute_path(filename, asset_subdir=subdir)
        if not path:
            raise RuntimeError(f"MPFB asset not found: {subdir}/{filename}")
        HumanService.add_mhclo_asset(path, body, asset_type=asset_type, material_type="GAMEENGINE")

    character_objects = {armature, body} | set(ObjectService.get_list_of_children(armature))
    for obj in tuple(bpy.context.scene.objects):
        if obj not in character_objects:
            bpy.data.objects.remove(obj, do_unlink=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    bpy.ops.file.pack_all()
    blend_path = output_dir / f"{recipe['character_id']}.blend"
    glb_path = output_dir / f"{recipe['character_id']}.glb"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))

    export_root = ExportService.create_character_copy(body, name_suffix="_export")
    export_body = ObjectService.find_object_of_type_amongst_nearest_relatives(export_root, "Basemesh")
    ExportService.bake_modifiers_remove_helpers(
        export_body, bake_masks=True, bake_subdiv=True, remove_helpers=True, also_proxy=True
    )
    bpy.ops.object.select_all(action="DESELECT")
    selected = [export_root] + ObjectService.get_list_of_children(export_root)
    for obj in selected:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = export_root
    bpy.ops.export_scene.gltf(
        filepath=str(glb_path), export_format="GLB", use_selection=True,
        export_animations=False, export_skins=True, export_apply=True,
        export_image_format="AUTO",
    )
    texture_images = [image for image in bpy.data.images if image.source == "FILE" and image.size[0] and image.size[1]]
    decoded_texture_bytes = sum(image.size[0] * image.size[1] * 4 for image in texture_images)
    manifest = {
        "schema": "atlas-mpfb-character-build/v1",
        "build_id": output_dir.name,
        "character_id": recipe["character_id"],
        "recipe": recipe,
        "recipe_sha256": hashlib.sha256(json.dumps(recipe, sort_keys=True).encode("utf-8")).hexdigest(),
        "generator": {"name": "MakeHuman Community MPFB", "version": "2.0.17", "blender": bpy.app.version_string},
        "asset_license": "MakeHuman core/system graphics assets are CC0; verify each selected module's source record.",
        "rig": {
            "name": "MPFB game_engine",
            "bone_count": len(armature.data.bones),
            "bone_names": [bone.name for bone in armature.data.bones],
            "animation_clips": [],
            "status": "Rigged; no Atlas animation retarget or deformation review has been completed.",
        },
        "shape_keys": {
            "count": max(0, len(body.data.shape_keys.key_blocks) - 1) if body.data.shape_keys else 0,
            "raw_names": [key.name for key in body.data.shape_keys.key_blocks if key.name != "Basis"] if body.data.shape_keys else [],
            "recipe_controls": sorted(recipe["macro"]),
        },
        "texture_memory_estimate": {
            "unique_image_count": len(texture_images),
            "decoded_rgba_mib": round(decoded_texture_bytes / (1024 ** 2), 2),
            "with_full_mip_chain_mib": round(decoded_texture_bytes * 4 / 3 / (1024 ** 2), 2),
            "images": [
                {"name": image.name, "width": image.size[0], "height": image.size[1], "format": image.file_format}
                for image in texture_images
            ],
            "caveat": "Estimate assumes RGBA8 GPU textures; actual usage depends on the target GPU and texture format.",
        },
        "outputs": {
            "blend": {"path": blend_path.name, "sha256": hashlib.sha256(blend_path.read_bytes()).hexdigest()},
            "glb": {"path": glb_path.name, "sha256": hashlib.sha256(glb_path.read_bytes()).hexdigest()},
        },
        "notes": [
            "Generated from an MPFB base and swappable CC0 system assets.",
            "Review visual quality, animation, clothing fit, and GLB shape-key behavior before runtime approval.",
        ],
    }
    (output_dir / "build.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"MPFB_BUILD_OK {blend_path} {glb_path}")


if __name__ == "__main__":
    arguments = parse_args()
    source = json.loads(arguments.recipe.read_text(encoding="utf-8"))
    validate_recipe(source)
    build(source, arguments.output_dir.resolve())
