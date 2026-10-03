"""Blender sidebar for selecting and moving Atlas character landmarks."""

bl_info = {
    "name": "Atlas Landmark Placement",
    "author": "Project Atlas",
    "version": (1, 0, 0),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar > Atlas Markers",
    "description": "Select and place named rig and face landmarks on an Atlas base model",
    "category": "3D View",
}

import hashlib
import json
from pathlib import Path

import bpy
from bpy.props import EnumProperty, StringProperty


MARKER_PREFIX = "ATLAS_MARKER_"


def marker_items(_self, _context):
    markers = sorted(
        (obj for obj in bpy.data.objects if obj.type == "EMPTY" and obj.name.startswith(MARKER_PREFIX)),
        key=lambda obj: obj.get("atlas.marker_role", obj.name),
    )
    return [(obj.name, obj.get("atlas.marker_role", obj.name), "Select this character landmark") for obj in markers]


def base_is_accepted(scene):
    record_path = scene.get("atlas.character_record_path")
    if not record_path:
        return False
    path = Path(record_path)
    if not path.is_absolute():
        path = Path(bpy.data.filepath).resolve().parent / path
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    quality = record.get("generation_quality")
    review = record.get("base_review")
    hashes = record.get("sha256")
    mesh = record.get("mesh")
    if not all(isinstance(value, dict) for value in (quality, review, hashes, mesh)):
        return False
    files = record.get("files")
    if not isinstance(files, dict) or not isinstance(files.get("preview_glb"), str):
        return False
    preview = path.parent / files["preview_glb"]
    try:
        current_preview_hash = hashlib.sha256(preview.read_bytes()).hexdigest()
    except OSError:
        return False
    return bool(
        record.get("base_review_status") == "accepted"
        and quality.get("tier") == "blockout_only"
        and quality.get("production_ready") is False
        and review.get("decision") == "accept"
        and review.get("approval_scope") == "rigging_candidate_only"
        and review.get("reviewed_sculpt") is True
        and review.get("reviewed_t_pose") is True
        and review.get("preview_sha256") == hashes.get("preview_glb")
        and current_preview_hash == hashes.get("preview_glb")
        and record.get("neutral_pose") == "t_pose_fingers_spread"
        and mesh.get("shoulder_core_connected") is True
    )


class ATLAS_OT_activate_marker(bpy.types.Operator):
    bl_idname = "atlas.activate_marker"
    bl_label = "Select Landmark"
    bl_description = "Select this landmark, then move it with G or the viewport gizmo"

    marker_name: StringProperty()

    def execute(self, context):
        if not base_is_accepted(context.scene):
            self.report({"WARNING"}, "Accept the visual base before placing rig markers")
            return {"CANCELLED"}
        marker = bpy.data.objects.get(self.marker_name)
        if marker is None or not marker.name.startswith(MARKER_PREFIX):
            self.report({"ERROR"}, "The selected Atlas marker no longer exists")
            return {"CANCELLED"}
        bpy.ops.object.select_all(action="DESELECT")
        marker.hide_select = False
        marker.hide_set(False)
        marker.select_set(True)
        context.view_layer.objects.active = marker
        try:
            bpy.ops.wm.tool_set_by_id(name="builtin.move")
        except RuntimeError:
            pass
        return {"FINISHED"}


class ATLAS_OT_focus_marker(bpy.types.Operator):
    bl_idname = "atlas.focus_marker"
    bl_label = "Frame Landmark"
    bl_description = "Frame the selected landmark in the 3D viewport"

    marker_name: StringProperty()

    def execute(self, context):
        marker = bpy.data.objects.get(self.marker_name)
        if marker is None:
            self.report({"ERROR"}, "The selected Atlas marker no longer exists")
            return {"CANCELLED"}
        bpy.ops.object.select_all(action="DESELECT")
        marker.select_set(True)
        context.view_layer.objects.active = marker
        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                with context.temp_override(area=area, region=next((r for r in area.regions if r.type == "WINDOW"), None)):
                    bpy.ops.view3d.view_selected(use_all_regions=False)
                return {"FINISHED"}
        return {"FINISHED"}


class ATLAS_PT_landmark_placement(bpy.types.Panel):
    bl_label = "Atlas Landmark Placement"
    bl_idname = "ATLAS_PT_landmark_placement"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Atlas Markers"

    def draw(self, context):
        layout = self.layout
        root = bpy.data.objects.get("ATLAS_GENERATED_CHARACTER_ROOT")
        if root is None:
            layout.label(text="Open a generated Atlas base model", icon="INFO")
            return
        layout.label(text=root.get("atlas.character_id", "Atlas character"), icon="OUTLINER_OB_ARMATURE")
        accepted = base_is_accepted(context.scene)
        layout.label(text="Base accepted" if accepted else "Base review required",
                     icon="CHECKMARK" if accepted else "INFO")
        if not accepted:
            layout.label(text="Marker movement unlocks after base approval")
        layout.separator()
        layout.label(text="Choose a landmark, then move it on the mesh.")
        markers = marker_items(None, context)
        if not markers:
            layout.label(text="No ATLAS_MARKER guides found", icon="ERROR")
            return
        layout.prop(context.scene, "atlas_selected_marker", text="Landmark")
        name = context.scene.atlas_selected_marker
        row = layout.row(align=True)
        activate = row.operator(ATLAS_OT_activate_marker.bl_idname, text="Select and Move", icon="ORIENTATION_GLOBAL")
        activate.marker_name = name
        focus = row.operator(ATLAS_OT_focus_marker.bl_idname, text="Frame", icon="ZOOM_SELECTED")
        focus.marker_name = name
        marker = bpy.data.objects.get(name)
        if marker:
            layout.separator()
            layout.label(text=f"Role: {marker.get('atlas.marker_role', 'unspecified')}")
            kind = marker.get("atlas.marker_kind", "joint_center")
            layout.label(text="Place on surface" if kind == "surface" else "Place at joint center")
            layout.label(text="G moves · X/Y/Z constrain · Esc cancels")
            layout.label(text="Use the gizmo for precise placement")


CLASSES = (ATLAS_OT_activate_marker, ATLAS_OT_focus_marker, ATLAS_PT_landmark_placement)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.atlas_selected_marker = EnumProperty(
        name="Landmark", description="Atlas rig or facial landmark", items=marker_items,
    )


def unregister():
    if hasattr(bpy.types.Scene, "atlas_selected_marker"):
        del bpy.types.Scene.atlas_selected_marker
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
