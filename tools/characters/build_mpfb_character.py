"""Build a modular, recipe-driven MakeHuman/MPFB character in Blender.

Run with Blender 4.2+ and MPFB/system assets installed:
  blender --background --python tools/characters/build_mpfb_character.py -- \
    --recipe art/characters/recipes/mpfb_prototype.json

The recipe is deliberately a narrow proof of concept. It selects supported
MPFB macro controls and swappable system assets; it does not infer geometry
from free-form text.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

ROOT = Path(__file__).resolve().parents[2]
MAX_RUNTIME_TEXTURE_DIMENSION = 1024
OPAQUE_CLOTHING_ASSETS = frozenset({"cortu_cargo_pants", "toigo_fisherman_sweater"})


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
    if args.output_dir is not None and not args.output_dir.is_absolute():
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


def hide_body_under_clothing(
    body,
    garments,
    distance_threshold: float = 0.025,
    opening_clearance: float = 0.04,
    neck_opening_clearance: float = 0.09,
) -> dict:
    """Mask body only well inside garments, preserving skin at open boundaries."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    body_points = [body.matrix_world @ vertex.co for vertex in body.data.vertices]
    covered_vertices: set[int] = set()
    measured_garments = []
    opening_protected = set()
    neck_opening_protected = set()

    for garment in garments:
        evaluated = garment.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            vertices = [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
            polygons = [list(polygon.vertices) for polygon in mesh.polygons]
            if not vertices or not polygons:
                continue
            tree = BVHTree.FromPolygons(vertices, polygons, all_triangles=False)
            edge_face_counts = {}
            for polygon in mesh.polygons:
                for edge_key in polygon.edge_keys:
                    key = tuple(sorted(edge_key))
                    edge_face_counts[key] = edge_face_counts.get(key, 0) + 1
            boundary_edges = [key for key, count in edge_face_counts.items() if count == 1]
            boundary_samples = []
            for first, second in boundary_edges:
                start, end = vertices[first], vertices[second]
                segments = max(1, math.ceil((end - start).length / 0.01))
                boundary_samples.extend(
                    start.lerp(end, step / segments)
                    for step in range(segments + 1)
                )
            boundary_tree = None
            if boundary_samples:
                boundary_tree = KDTree(len(boundary_samples))
                for sample_index, sample in enumerate(boundary_samples):
                    boundary_tree.insert(sample, sample_index)
                boundary_tree.balance()
            sweater_hem_z = None
            if "toigo_fisherman_sweater" in garment.name:
                torso_z = [
                    (garment.matrix_world @ vertex.co).z
                    for vertex in mesh.vertices
                    if abs((evaluated.matrix_world @ vertex.co).x) < 0.12
                ]
                sweater_hem_z = min(torso_z) if torso_z else None
            garment_coverage = set()
            for index, point in enumerate(body_points):
                nearest = tree.find_nearest(point)
                if nearest:
                    is_sweater_hem = False
                    boundary_nearest = boundary_tree.find(point) if boundary_tree else None
                    is_sweater_collar = False
                    if boundary_tree and sweater_hem_z is not None:
                        is_sweater_hem = (
                            boundary_nearest[2] < opening_clearance
                            and abs(point.x) < 0.24
                            and abs(boundary_nearest[0].x) < 0.24
                            and boundary_nearest[0].z < sweater_hem_z + 0.15
                        )
                        is_sweater_collar = (
                            abs(point.x) < 0.20
                            and abs(boundary_nearest[0].x) < 0.20
                            and boundary_nearest[0].z > sweater_hem_z + 0.30
                        )
                    effective_distance = 0.04 if is_sweater_hem else distance_threshold
                    if nearest[3] > effective_distance:
                        continue
                    effective_opening_clearance = (
                        neck_opening_clearance if is_sweater_collar else opening_clearance
                    )
                    if boundary_nearest and boundary_nearest[2] < effective_opening_clearance and not is_sweater_hem:
                        opening_protected.add(index)
                        if is_sweater_collar:
                            neck_opening_protected.add(index)
                        continue
                    garment_coverage.add(index)
            covered_vertices.update(garment_coverage)
            measured_garments.append({"object": garment.name, "near_body_vertices": len(garment_coverage)})
        finally:
            evaluated.to_mesh_clear()

    group_name = "Atlas.HideBodyUnderClothing"
    group = body.vertex_groups.get(group_name) or body.vertex_groups.new(name=group_name)
    if covered_vertices:
        group.add(sorted(covered_vertices), 1.0, "REPLACE")
    modifier_name = "Atlas Clothing Occlusion"
    modifier = body.modifiers.get(modifier_name) or body.modifiers.new(modifier_name, "MASK")
    modifier.vertex_group = group.name
    modifier.invert_vertex_group = True
    return {
        "distance_threshold_m": distance_threshold,
        "open_boundary_clearance_m": opening_clearance,
        "neck_opening_clearance_m": neck_opening_clearance,
        "body_vertices_hidden": len(covered_vertices),
        "body_vertices_protected_near_openings": len(opening_protected),
        "body_vertices_protected_near_sweater_neck": len(neck_opening_protected),
        "garments": measured_garments,
        "boundary_policy": "preserve open collar/cuff vertices; mask the sweater hem where pants overlap",
    }


def make_mesh_material_opaque(mesh_objects) -> None:
    """Mark only the body and solid clothing passed here as opaque.

    Hair, eyes, brows, lashes, and teeth are intentionally excluded so their
    source alpha maps remain connected for GLB export.
    """
    seen = set()
    for obj in mesh_objects:
        for material in obj.data.materials:
            if not material or material.as_pointer() in seen or not material.use_nodes:
                continue
            seen.add(material.as_pointer())
            shader = next((node for node in material.node_tree.nodes if node.type == "BSDF_PRINCIPLED"), None)
            if not shader:
                continue
            alpha = shader.inputs.get("Alpha")
            if not alpha:
                continue
            for link in tuple(alpha.links):
                material.node_tree.links.remove(link)
            alpha.default_value = 1.0


def fit_pants_under_sweater(recipe: dict, garments) -> dict | None:
    """Trim the pants to the generated sweater's curved hem profile."""
    if recipe.get("shirt") != "toigo_fisherman_sweater" or recipe.get("pants") != "cortu_cargo_pants":
        return None
    shirt = next((obj for obj in garments if recipe["shirt"] in obj.name), None)
    pants = next((obj for obj in garments if recipe["pants"] in obj.name), None)
    if shirt is None or pants is None:
        raise RuntimeError("Expected sweater/high-rise pants objects were not created by MPFB")

    world_vertices = [shirt.matrix_world @ vertex.co for vertex in shirt.data.vertices]
    shirt_hem = min(point.z for point in world_vertices if abs(point.x) < 0.12)
    pants_top = max((pants.matrix_world @ vertex.co).z for vertex in pants.data.vertices)
    # Find the connected, closed boundary loop at the bottom of this exact
    # generated sweater. Its height changes with the MPFB body proportions.
    edge_face_counts = {}
    for polygon in shirt.data.polygons:
        for edge_key in polygon.edge_keys:
            key = tuple(sorted(edge_key))
            edge_face_counts[key] = edge_face_counts.get(key, 0) + 1
    candidate_edges = []
    for edge, count in edge_face_counts.items():
        if count != 1:
            continue
        a, b = (world_vertices[index] for index in edge)
        if max(a.z, b.z) <= shirt_hem + 0.08 and abs(a.x) < 0.30 and abs(b.x) < 0.30:
            candidate_edges.append(edge)
    adjacency = {}
    for a, b in candidate_edges:
        adjacency.setdefault(a, set()).add(b)
        adjacency.setdefault(b, set()).add(a)
    components = []
    component_sizes = []
    unseen = set(adjacency)
    while unseen:
        seed = unseen.pop()
        component = {seed}
        pending = [seed]
        while pending:
            current = pending.pop()
            for neighbor in adjacency[current] & unseen:
                unseen.remove(neighbor)
                component.add(neighbor)
                pending.append(neighbor)
        is_closed_loop = all(len(adjacency[index] & component) == 2 for index in component)
        component_sizes.append({"vertices": len(component), "closed": is_closed_loop})
        if len(component) >= 8 and is_closed_loop:
            components.append(component)
    if not components:
        raise RuntimeError(
            "Could not find a closed sweater hem loop for curved pants fitting; "
            + json.dumps({
                "candidate_boundary_edges": len(candidate_edges),
                "candidate_components": component_sizes,
            })
        )
    hem_loop = min(components, key=lambda comp: sum(world_vertices[i].z for i in comp) / len(comp))
    first = min(hem_loop)
    ordered_loop = [first]
    previous = None
    current = first
    while True:
        following = next(index for index in adjacency[current] if index != previous)
        if following == first:
            break
        if following in ordered_loop:
            raise RuntimeError("Sweater hem boundary loop is not a simple ring")
        ordered_loop.append(following)
        previous, current = current, following
    if len(ordered_loop) != len(hem_loop):
        raise RuntimeError("Could not order the complete sweater hem boundary")

    pants_overlap_above_hem = 0.01
    radial_margin = 0.05
    pants_vertices_before_fit = len(pants.data.vertices)
    pants_faces_before_fit = len(pants.data.polygons)
    pants_height_before_fit = pants.dimensions.z
    pants_dimensions_before_fit = tuple(pants.dimensions)
    ring = [world_vertices[index].copy() for index in ordered_loop]
    center_x = sum(point.x for point in ring) / len(ring)
    center_y = sum(point.y for point in ring) / len(ring)
    lower_ring = []
    for point in ring:
        dx, dy = point.x - center_x, point.y - center_y
        radial_length = math.hypot(dx, dy) or 1.0
        lower_ring.append((
            point.x + dx / radial_length * radial_margin,
            point.y + dy / radial_length * radial_margin,
            point.z + pants_overlap_above_hem,
        ))
    cutter_top = max(pants_top + 0.05, max(point[2] for point in lower_ring) + 0.05)
    count = len(lower_ring)
    cutter_vertices = lower_ring + [(x, y, cutter_top) for x, y, _ in lower_ring]
    cutter_faces = [tuple(reversed(range(count))), tuple(range(count, count * 2))]
    cutter_faces.extend(
        (index, (index + 1) % count, (index + 1) % count + count, index + count)
        for index in range(count)
    )
    cutter_mesh = bpy.data.meshes.new("Atlas.CurvedWaistCut.mesh")
    cutter_mesh.from_pydata(cutter_vertices, [], cutter_faces)
    cutter_mesh.update()
    cutter = bpy.data.objects.new("Atlas.CurvedWaistCut", cutter_mesh)
    bpy.context.scene.collection.objects.link(cutter)
    bm = bmesh.new()
    bm.from_mesh(cutter_mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(cutter_mesh)
    bm.free()

    modifier = pants.modifiers.new("Atlas Curved Sweater Waist Fit", "BOOLEAN")
    modifier_name = modifier.name
    modifier.operation = "DIFFERENCE"
    modifier.solver = "EXACT"
    modifier.object = cutter
    try:
        bpy.ops.object.select_all(action="DESELECT")
        pants.select_set(True)
        bpy.context.view_layer.objects.active = pants
        result = bpy.ops.object.modifier_apply(modifier=modifier_name)
        if "FINISHED" not in result:
            raise RuntimeError("Could not apply curved sweater-to-pants waist fit")
    finally:
        existing_modifier = pants.modifiers.get(modifier_name)
        if existing_modifier:
            pants.modifiers.remove(existing_modifier)
        bpy.data.objects.remove(cutter, do_unlink=True)
        bpy.data.meshes.remove(cutter_mesh)

    pants.data.update()
    if not pants.data.polygons:
        raise RuntimeError("Curved sweater waist fit removed the complete pants mesh")
    pants_vertices_after_fit = len(pants.data.vertices)
    pants_faces_after_fit = len(pants.data.polygons)
    pants_height_after_fit = pants.dimensions.z
    vertex_retention = pants_vertices_after_fit / max(1, pants_vertices_before_fit)
    face_retention = pants_faces_after_fit / max(1, pants_faces_before_fit)
    height_retention = pants_height_after_fit / max(1e-9, pants_height_before_fit)
    fit_diagnostics = {
        "pants_vertices_before_fit": pants_vertices_before_fit,
        "pants_vertices_after_fit": pants_vertices_after_fit,
        "pants_vertex_retention_pct": round(vertex_retention * 100, 2),
        "pants_vertices_removed_pct": round(max(0.0, 1.0 - vertex_retention) * 100, 2),
        "pants_faces_before_fit": pants_faces_before_fit,
        "pants_faces_after_fit": pants_faces_after_fit,
        "pants_face_retention_pct": round(face_retention * 100, 2),
        "pants_faces_removed_pct": round(max(0.0, 1.0 - face_retention) * 100, 2),
        "pants_dimensions_before_fit_m": [round(value, 4) for value in pants_dimensions_before_fit],
        "pants_vertical_retention_pct": round(height_retention * 100, 2),
    }
    # Boolean cutters can occasionally classify a mesh incorrectly. Do not
    # save/export a candidate if it has removed most of the pants or shortened
    # the legs; retain these diagnostics in the raised error for review.
    if vertex_retention < 0.50 or face_retention < 0.50 or height_retention < 0.75:
        raise RuntimeError(
            "Curved sweater waist fit removed too much pants geometry: "
            + json.dumps(fit_diagnostics, sort_keys=True)
        )
    return {
        "shirt": shirt.name,
        "pants": pants.name,
        "pants_top_world_z_m": round(pants_top, 4),
        "shirt_hem_world_z_m": round(shirt_hem, 4),
        "shirt_hem_height_range_world_m": [
            round(min(point.z for point in ring), 4),
            round(max(point.z for point in ring), 4),
        ],
        "pants_overlap_above_sweater_hem_m": pants_overlap_above_hem,
        "cutter_radial_margin_m": radial_margin,
        **fit_diagnostics,
        "pants_dimensions_after_fit_m": [round(value, 4) for value in pants.dimensions],
        "hem_loop_vertices": len(ring),
        "candidate_boundary_edges": len(candidate_edges),
        "candidate_components": component_sizes,
        "closed_hem_components": len(components),
        "selected_hem_component_vertices": len(hem_loop),
        "method": "boolean trim follows this generated sweater hem loop",
    }


def measure_garment_intersections(garments) -> dict:
    """Count triangle-pair intersections between generated garment surfaces."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    garment_trees = []
    for garment in garments:
        evaluated = garment.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            vertices = [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
            polygons = [list(polygon.vertices) for polygon in mesh.polygons]
            tree = BVHTree.FromPolygons(vertices, polygons, all_triangles=False) if vertices and polygons else None
            garment_trees.append((garment.name, tree))
        finally:
            evaluated.to_mesh_clear()

    pairs = []
    for first_index, (first_name, first_tree) in enumerate(garment_trees):
        for second_name, second_tree in garment_trees[first_index + 1:]:
            intersections = first_tree.overlap(second_tree) if first_tree and second_tree else []
            pairs.append({
                "objects": [first_name, second_name],
                "triangle_pair_count": len(intersections),
            })
    return {
        "pairs": pairs,
        "total_triangle_pair_count": sum(pair["triangle_pair_count"] for pair in pairs),
        "note": "Counts intersecting triangle pairs; touching/coincident surfaces may count, so review per garment pair.",
    }


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
    # MPFB's game-engine preset enables Blender's "In Front" armature display,
    # which makes rig controls look like transparent holes through the face.
    armature.show_in_front = False
    for bone in armature.data.bones:
        if bone.name == "Root":
            bone.name = "root"
            break

    garments = []
    face_detail_objects = []
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
        added_asset = HumanService.add_mhclo_asset(
            path, body, asset_type=asset_type, material_type="GAMEENGINE"
        )
        if subdir == "clothes":
            garments.append(added_asset)
        elif subdir in {"eyes", "eyebrows", "eyelashes", "teeth", "hair"}:
            face_detail_objects.append(added_asset)

    garment_fit_adjustment = fit_pants_under_sweater(recipe, garments)
    garment_intersections = measure_garment_intersections(garments)
    clothing_occlusion = hide_body_under_clothing(body, garments)
    opaque_clothing = [
        garment for garment in garments
        if any(asset_name in garment.name for asset_name in OPAQUE_CLOTHING_ASSETS)
    ]
    alpha_preserved_clothing = [garment for garment in garments if garment not in opaque_clothing]
    make_mesh_material_opaque([body, *opaque_clothing])

    character_objects = {armature, body} | set(ObjectService.get_list_of_children(armature))
    for obj in tuple(bpy.context.scene.objects):
        if obj not in character_objects:
            bpy.data.objects.remove(obj, do_unlink=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    # Keep repeated local rebuilds from accumulating stale .blend1 backups.
    bpy.context.preferences.filepaths.save_version = 0
    # MPFB's current outfit meshes have open or inconsistent winding around
    # garment edges. Keep character surfaces double-sided until each source
    # asset is validated and normalized independently.
    double_sided_materials = set()
    for obj in (body, *face_detail_objects, *garments):
        for material in obj.data.materials:
            if material:
                material.use_backface_culling = False
                double_sided_materials.add(material.name)
    bpy.ops.file.pack_all()
    blend_path = output_dir / f"{recipe['character_id']}.blend"
    glb_path = output_dir / f"{recipe['character_id']}.glb"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))

    export_root = ExportService.create_character_copy(body, name_suffix="_export")
    export_body = ObjectService.find_object_of_type_amongst_nearest_relatives(export_root, "Basemesh")
    ExportService.bake_modifiers_remove_helpers(
        export_body, bake_masks=True, bake_subdiv=True, remove_helpers=True, also_proxy=True
    )
    # Keep the editable .blend at source resolution, but limit the standalone
    # runtime GLB's texture decode, GPU upload, and memory costs.
    for image in bpy.data.images:
        if image.source != "FILE" or not image.size[0] or not image.size[1]:
            continue
        width, height = image.size
        longest_edge = max(width, height)
        if longest_edge <= MAX_RUNTIME_TEXTURE_DIMENSION:
            continue
        # Hairline alpha needs the source 2K texture to avoid visible stair
        # steps at close range. Keep other maps capped at 1K for memory.
        texture_limit = 2048 if "ponytail" in image.name.lower() else MAX_RUNTIME_TEXTURE_DIMENSION
        scale = texture_limit / longest_edge
        image.scale(max(1, round(width * scale)), max(1, round(height * scale)))
        image.pack()
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
        "build_id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ"),
        "character_id": recipe["character_id"],
        "recipe": recipe,
        "recipe_sha256": hashlib.sha256(json.dumps(recipe, sort_keys=True).encode("utf-8")).hexdigest(),
        "generator": {
            "name": "MakeHuman Community MPFB",
            "version": "2.0.17",
            "blender": bpy.app.version_string,
            "mpfb_scale_factor": 0.1,
            "coordinate_units": "meters",
            "generated_body_dimensions_m": [round(value, 4) for value in body.dimensions],
        },
        "material_policy": {
            "opaque_material_objects": [body.name, *(obj.name for obj in opaque_clothing)],
            "opaque_clothing_assets": sorted(
                asset_name for asset_name in OPAQUE_CLOTHING_ASSETS
                if any(asset_name in obj.name for obj in opaque_clothing)
            ),
            "alpha_preserved_objects": [
                obj.name for obj in (*face_detail_objects, *alpha_preserved_clothing)
            ],
            "double_sided_materials": sorted(double_sided_materials),
            "reason": "current MPFB clothing assets have open or inconsistent edge winding",
        },
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
            "runtime_max_dimension": MAX_RUNTIME_TEXTURE_DIMENSION,
            "high_detail_texture_exceptions": {"ponytail": 2048},
            "images": [
                {"name": image.name, "width": image.size[0], "height": image.size[1], "format": image.file_format}
                for image in texture_images
            ],
            "caveat": "Estimate assumes RGBA8 GPU textures; actual usage depends on the target GPU and texture format.",
        },
        "clothing_occlusion": clothing_occlusion,
        "garment_fit_adjustment": garment_fit_adjustment,
        "garment_intersections": garment_intersections,
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
    # GLB stores no Blender viewport armature-display flag. Make a companion
    # Blender inspection file automatically, with rig bones hidden by default,
    # so the exported asset opens cleanly in Blender too.
    characters_tool_dir = str(Path(__file__).resolve().parent)
    if characters_tool_dir not in sys.path:
        sys.path.insert(0, characters_tool_dir)
    from prepare_gltf_blender_view import prepare_view

    prepare_view(glb_path, output_dir / f"{recipe['character_id']}_blender_view.blend")
    print(f"MPFB_BUILD_OK {blend_path} {glb_path}")


if __name__ == "__main__":
    arguments = parse_args()
    source = json.loads(arguments.recipe.read_text(encoding="utf-8"))
    validate_recipe(source)
    if arguments.output_dir is None:
        arguments.output_dir = ROOT / "art/characters/exports" / source["character_id"]
    build(source, arguments.output_dir.resolve())
