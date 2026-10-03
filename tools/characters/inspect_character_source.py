#!/usr/bin/env python3
"""Create a technical source dossier and an explicitly unreviewed observation draft.

Run with Blender 4.x+:
  blender --background --python tools/characters/inspect_character_source.py -- \
    --source /path/model.glb --archetype-id humanoid --independent-source-id creator:model \
    --output-dir art/characters/recipe_observations/drafts/model

This script inventories geometry. It does not infer anatomy or approve rights/quality.
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

VERSION = "1.0.0"
ROOT = Path(__file__).resolve().parents[2]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def gltf_companions(path: Path):
    """Hash local glTF buffer/image dependencies without following data/http URIs."""
    if path.suffix.lower() != ".gltf":
        return []
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    uris = set()
    for item in doc.get("buffers", []) + doc.get("images", []):
        uri = item.get("uri")
        if uri and not uri.startswith(("data:", "http:", "https:")):
            uris.add(uri)
    files = []
    for uri in sorted(uris):
        dep = (path.parent / uri).resolve()
        if dep.is_file():
            files.append({"path": str(dep), "sha256": sha256(dep), "bytes": dep.stat().st_size})
    return files


def vec(v):
    return [round(float(x), 8) for x in v]


def bounds(obj):
    if obj.type != "MESH" or not obj.data.vertices:
        return None
    points = [obj.matrix_world @ Vector(p) for p in obj.bound_box]
    low = [min(p[i] for p in points) for i in range(3)]
    high = [max(p[i] for p in points) for i in range(3)]
    return {"low": vec(low), "high": vec(high), "dimensions": vec([high[i] - low[i] for i in range(3)])}


def connected_components(mesh):
    n = len(mesh.vertices)
    parent = list(range(n))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for edge in mesh.edges:
        a, b = find(edge.vertices[0]), find(edge.vertices[1])
        if a != b:
            parent[b] = a
    counts = {}
    for i in range(n):
        root = find(i)
        counts[root] = counts.get(root, 0) + 1
    return sorted(counts.values(), reverse=True)


def mesh_record(obj, depsgraph):
    mesh = obj.data
    driver_curves = []
    for curve in (obj.animation_data.drivers if obj.animation_data else []):
        variables = []
        for var in curve.driver.variables:
            targets = []
            for target in var.targets:
                targets.append({"id_name": target.id.name if target.id else None,
                                "data_path": target.data_path,
                                "bone_target": target.bone_target})
            variables.append({"name": var.name, "type": var.type, "targets": targets})
        unresolved = any(target["id_name"] is None for variable in variables for target in variable["targets"])
        driver_curves.append({"data_path": curve.data_path, "array_index": curve.array_index,
                              "is_valid": bool(curve.is_valid), "has_unresolved_targets": unresolved,
                              "expression": curve.driver.expression, "variables": variables})
    evaluated_geometry_reliable = not any(
        not curve["is_valid"] or curve["has_unresolved_targets"] for curve in driver_curves
    )
    bm = None
    try:
        import bmesh
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bm.edges.ensure_lookup_table()
        boundary = sum(1 for edge in bm.edges if len(edge.link_faces) == 1)
        nonmanifold = sum(1 for edge in bm.edges if not edge.is_manifold)
        wire = sum(1 for edge in bm.edges if not edge.link_faces)
        bm.free()
    except Exception:
        if bm:
            bm.free()
        boundary = nonmanifold = wire = 0
    triangles = sum(max(0, len(poly.vertices) - 2) for poly in mesh.polygons)
    try:
        evaluated = obj.evaluated_get(depsgraph)
        eval_mesh = evaluated.to_mesh()
        eval_vertices, eval_polygons = len(eval_mesh.vertices), len(eval_mesh.polygons)
        evaluated.to_mesh_clear()
    except Exception:
        eval_vertices = eval_polygons = None
    groups = []
    for group in obj.vertex_groups:
        assigned = 0
        for vertex in mesh.vertices:
            for assignment in vertex.groups:
                if assignment.group == group.index and assignment.weight > 0:
                    assigned += 1
                    break
        groups.append({"name": group.name, "assigned_vertex_count": assigned})
    materials = []
    for slot in obj.material_slots:
        mat = slot.material
        image_refs = []
        if mat and mat.use_nodes:
            for node in mat.node_tree.nodes:
                if node.type == "TEX_IMAGE" and node.image:
                    image = node.image
                    image_refs.append({"name": image.name, "filepath": image.filepath, "packed": bool(image.packed_file)})
        materials.append({"name": mat.name if mat else None, "image_textures": image_refs})
    attrs = [{"name": a.name, "domain": a.domain, "data_type": a.data_type} for a in mesh.attributes]
    return {
        "name": obj.name, "mesh_data_name": mesh.name,
        "vertex_count": len(mesh.vertices), "edge_count": len(mesh.edges),
        "polygon_count": len(mesh.polygons), "triangle_count": triangles,
        "evaluated_vertex_count": eval_vertices, "evaluated_polygon_count": eval_polygons,
        "evaluated_geometry_reliable": evaluated_geometry_reliable, "driver_curves": driver_curves,
        "world_bounds": bounds(obj),
        "topology": {"connected_component_count": len(connected_components(mesh)),
                     "largest_component_vertex_counts": connected_components(mesh)[:10],
                     "boundary_edge_count": boundary, "non_manifold_edge_count": nonmanifold,
                     "wire_edge_count": wire},
        "normals": {"zero_area_polygon_count": sum(1 for p in mesh.polygons if p.area <= 1e-12)},
        "modifiers": [{"name": m.name, "type": m.type, "show_viewport": bool(m.show_viewport), "show_render": bool(m.show_render)} for m in obj.modifiers],
        "vertex_groups": groups,
        "uv_layers": [layer.name for layer in mesh.uv_layers],
        "color_attributes": [a.name for a in mesh.color_attributes],
        "mesh_attributes": attrs, "material_slots": materials,
    }


def scene_object(obj):
    b = bounds(obj)
    return {"name": obj.name, "type": obj.type, "parent": obj.parent.name if obj.parent else None,
            "location": vec(obj.location), "rotation_euler": vec(obj.rotation_euler), "scale": vec(obj.scale),
            "world_bounds": b}


def shape_profile(obj):
    mesh = obj.data
    coords = [obj.matrix_world @ v.co for v in mesh.vertices]
    if not coords:
        return None, None
    zmin, zmax = min(p.z for p in coords), max(p.z for p in coords)
    height = zmax - zmin
    if height <= 1e-9:
        return None, None
    xmid = (min(p.x for p in coords) + max(p.x for p in coords)) / 2
    ymid = (min(p.y for p in coords) + max(p.y for p in coords)) / 2
    # Virtual normalization only: center XY, put the floor at Z=0, and set
    # world-Z height to one unit. The source scene and mesh datablocks stay intact.
    normalized = [((p.x-xmid)/height, (p.y-ymid)/height, (p.z-zmin)/height) for p in coords]
    sections = []
    for pct in range(0, 101, 5):
        z = pct / 100
        pts = [p for p in normalized if abs(p[2] - z) <= 0.025]
        if not pts:
            sections.append({"height_percent": pct, "sample_vertex_count": 0,
                             "x_extent_over_height": 0, "y_extent_over_height": 0,
                             "center_x_over_height": 0, "center_y_over_height": 0})
            continue
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        sections.append({"height_percent": pct, "sample_vertex_count": len(pts),
                         "x_extent_over_height": round(max(xs)-min(xs), 8),
                         "y_extent_over_height": round(max(ys)-min(ys), 8),
                         "center_x_over_height": round((max(xs)+min(xs))/2, 8),
                         "center_y_over_height": round((max(ys)+min(ys))/2, 8)})
    return height, {"object_name": obj.name, "axis": "world_z",
                    "normalization_basis": "focus_mesh_world_z_height",
                    "origin_policy": "center_xy_floor_z",
                    "normalized_height": 1.0, "sections": sections}


def import_source(path: Path):
    ext = path.suffix.lower()
    if ext == ".blend":
        bpy.ops.wm.open_mainfile(filepath=str(path))
    elif ext in (".glb", ".gltf"):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=str(path))
    else:
        raise ValueError("Supported formats are .blend, .glb, and .gltf")


def args_after_separator():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", required=True, type=Path)
    p.add_argument("--archetype-id", required=True)
    p.add_argument("--independent-source-id", required=True, help="Stable lineage key shared by variants/derivatives of one original source")
    p.add_argument("--output-dir", required=True, type=Path)
    p.add_argument("--focus-object")
    p.add_argument("--observation-id")
    p.add_argument("--source-title")
    p.add_argument("--source-author")
    p.add_argument("--source-license")
    p.add_argument("--source-url")
    return p.parse_args(argv)


def main():
    a = args_after_separator()
    source = a.source.expanduser().resolve()
    if not source.is_file():
        raise SystemExit("Source file does not exist: " + str(source))
    if not a.archetype_id or not a.independent_source_id:
        raise SystemExit("archetype-id and independent-source-id must be non-empty")
    if a.archetype_id != "humanoid":
        raise SystemExit("v1 anatomy vocabulary and height normalization currently support humanoid sources only")
    import_source(source)
    # .blend asset libraries may keep reusable objects outside the active scene.
    # Include every object datablock in the file so the dossier covers those too.
    objects = sorted(bpy.data.objects, key=lambda o: o.name.casefold())
    meshes = sorted((o for o in objects if o.type == "MESH"), key=lambda o: o.name.casefold())
    focus = next((o for o in meshes if o.name == a.focus_object), None) if a.focus_object else (meshes[0] if len(meshes) == 1 else None)
    if a.focus_object and focus is None:
        raise SystemExit("Requested focus mesh not found: " + a.focus_object)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    counts = {}
    for obj in objects:
        counts[obj.type] = counts.get(obj.type, 0) + 1
    source_hash = sha256(source)
    output = a.output_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    limitations = [
        "All semantic anatomy feature states are unknown in the draft; no anatomy was inferred.",
        "Geometry statistics do not establish visual quality, design fit, deformation suitability, or rights clearance.",
        "The normalized shape profile samples whole-mesh world-Z cross-sections; sections are not semantic body measurements.",
        "Connected-component counts use mesh edges and do not classify intentional islands.",
        "Rights status is always review_required regardless of supplied metadata.",
    ]
    scene = bpy.context.scene
    dossier = {
        "schema": "atlas-character-source-inspection/v1",
        "tool": {"name": "inspect_character_source.py", "version": VERSION, "blender_version": bpy.app.version_string},
        "source": {"path": str(source), "sha256": source_hash, "format": source.suffix.lower()[1:],
                   "companion_files": gltf_companions(source)},
        "provenance_claims": {"title": a.source_title, "creator": a.source_author, "source_url": a.source_url,
                              "license_label": a.source_license, "rights_review_status": "review_required"},
        "scene": {"name": scene.name, "unit_system": scene.unit_settings.system,
                  "unit_scale": float(scene.unit_settings.scale_length), "up_axis": "Z", "object_counts": counts,
                  "objects": [scene_object(o) for o in objects]},
        "mesh_objects": [mesh_record(o, depsgraph) for o in meshes],
        "armatures": [{"name": o.name, "bone_count": len(o.data.bones),
                       "bones": [{"name": b.name, "parent": b.parent.name if b.parent else None,
                                  "head": vec(b.head_local), "tail": vec(b.tail_local), "use_deform": bool(b.use_deform)}
                                 for b in o.data.bones]} for o in objects if o.type == "ARMATURE"],
        "actions": [{"name": act.name, "frame_start": float(act.frame_range[0]), "frame_end": float(act.frame_range[1])}
                    for act in sorted(bpy.data.actions, key=lambda x: x.name.casefold())],
        "focus_object": focus.name if focus else None,
        "normalized_shape_profile": shape_profile(focus)[1] if focus else None,
        "limitations": limitations,
    }
    inspection_path = output / "source_inspection.json"
    inspection_path.write_text(json.dumps(dossier, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    vocab_path = ROOT / "specs/atlas-character-observation-vocabulary-v1.json"
    vocab = json.loads(vocab_path.read_text(encoding="utf-8"))
    ids = [x["concept_id"] for x in vocab["concepts"]]
    measurements = []
    if focus:
        height, _ = shape_profile(focus)
        box = bounds(focus)
        if height and box:
            dx, dy = box["dimensions"][0], box["dimensions"][1]
            measurements = [
                {"measurement_id": "overall_width_over_height", "value": round(dx/height, 8),
                 "normalization": "focus mesh world-Z height", "method": "world-axis-aligned bounding-box dimensions", "review_status": "draft"},
                {"measurement_id": "overall_depth_over_height", "value": round(dy/height, 8),
                 "normalization": "focus mesh world-Z height", "method": "world-axis-aligned bounding-box dimensions", "review_status": "draft"},
            ]
    obs_id = a.observation_id or ("obs-" + re.sub(r"[^a-z0-9_.-]+", "-", source.stem.lower()).strip("-._")[:60])
    observation = {
        "schema": "atlas-character-observation/v1", "observation_id": obs_id,
        "archetype_id": a.archetype_id,
        "taxonomy_revision": int(vocab["revision"]),
        "source": {"kind": "model", "reference": str(source), "sha256": source_hash,
                   "creator": a.source_author or "unknown", "license": a.source_license or "unknown",
                   "rights_status": "review_required"},
        "lineage": {"independent_source_id": a.independent_source_id,
                    "notes": "Set this ID consistently for variants and derivatives from the same original source."},
        "review": {"status": "draft"},
        "features": {"present": [], "absent": [], "unknown": ids, "not_applicable": []},
        "measurements": measurements, "relationships": [],
        "evidence_files": [{"role": "source_inspection", "path": inspection_path.name, "sha256": sha256(inspection_path)}],
        "notes": "Machine-generated intake draft. Human review is required for anatomy labels, measurements, source lineage, and rights evidence.",
    }
    observation_path = output / "observation.draft.json"
    observation_path.write_text(json.dumps(observation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"source_inspection": str(inspection_path), "observation_draft": str(observation_path),
                      "source_sha256": source_hash, "focus_object": dossier["focus_object"]}, indent=2))


if __name__ == "__main__":
    main()
