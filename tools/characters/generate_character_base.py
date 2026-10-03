"""Build an Atlas character base from a profile using Blender geometry or a licensed seed.

Run with the repository's Blender version:
  blender --background --python tools/characters/generate_character_base.py -- \
    --profile art/characters/profiles/stone_troll.json

By default, the body is built from profile-scaled parametric forms. A reviewed
reference mesh can instead seed the body; its exact file, object, calibration,
and human rights/geometry review are pinned in the profile and build plan. The
source geometry is normalized, posed to the Atlas T-pose where its rig permits,
and baked without carrying over the source rig or animation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Euler, Matrix, Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/characters"))
from character_topology import TopologyValidationError, validate_shoulder_core  # noqa: E402
from character_image_reference import fit_mesh_to_front_profile, measure_front_reference  # noqa: E402


MARKER_PREFIX = "ATLAS_MARKER_"
PROFILE_SCHEMA = "atlas-character-design-profile/v1"
GENERATOR_VERSION = "atlas-character-base/v28"
DEFAULT_NEUTRAL_POSE = "t_pose_fingers_spread"

# Archetype modifiers are deterministic silhouette priors. Explicit profile
# controls remain the source of truth and are applied on top of these subtle
# defaults, so an AI-authored profile can override the stereotype.
ARCHETYPE_PRIORS = {
    "humanoid": {"jaw": 1.0, "hand": 1.0, "foot": 1.0, "ear": 1.0, "nose": 1.0, "head": 1.0},
    "troll": {"jaw": 1.03, "hand": 1.04, "foot": 1.03, "ear": 1.05, "nose": 1.04, "head": 1.0},
    "orc": {"jaw": 1.16, "hand": 1.08, "foot": 1.04, "ear": 1.0, "nose": 1.10, "head": 1.04},
    "elf": {"jaw": 0.96, "hand": 0.96, "foot": 1.0, "ear": 1.12, "nose": 0.96, "head": 1.0},
    "goblin": {"jaw": 0.96, "hand": 1.12, "foot": 0.96, "ear": 1.12, "nose": 1.04, "head": 1.08},
}


def arguments() -> argparse.Namespace:
    if "--" not in sys.argv:
        raise SystemExit("Pass generator options after --. See the script header.")
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--profile", type=Path, help="Design profile for a direct blockout build")
    inputs.add_argument(
        "--build-plan", type=Path,
        help="Frozen atlas-character-geometry-build-plan/v1 compiled from a profile and recipe",
    )
    parser.add_argument("--output-root", type=Path, default=ROOT / "art/characters/pending_models")
    parser.add_argument(
        "--allow-blockout", action="store_true",
        help="Explicitly generate the low-detail procedural concept mesh; this is not a production character.",
    )
    parser.add_argument(
        "--reference-model", "--reference-glb", dest="reference_model", type=Path,
        help="Optional .glb/.blend geometry seed; it must match an approved profile geometry-seed record.",
    )
    parser.add_argument(
        "--reference-image", type=Path,
        help="Fit the procedural body to a front-view image silhouette without AI or remote services.",
    )
    parser.add_argument(
        "--image-fit-strength", type=float, default=0.85,
        help="Silhouette fit amount between 0 and 1 (default: 0.85).",
    )
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])


def load_profile(path: Path) -> dict:
    sys.path.insert(0, str(ROOT / "tools/characters"))
    from character_design_profile import load_profile as validate

    profile = validate(path)
    if profile["schema"] != PROFILE_SCHEMA:
        raise ValueError(f"Expected {PROFILE_SCHEMA}")
    return profile


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def resolve_project_path(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def load_geometry_build_plan(path: Path) -> tuple[dict, dict]:
    """Verify a frozen plan and all recorded inputs before building its snapshot."""
    plan_path = path.expanduser().resolve(strict=True)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if not isinstance(plan, dict) or plan.get("schema") != "atlas-character-geometry-build-plan/v1":
        raise ValueError("unsupported or malformed character geometry build plan")
    recorded_plan_hash = plan.get("plan_sha256")
    unhashed_plan = dict(plan)
    unhashed_plan.pop("plan_sha256", None)
    if not isinstance(recorded_plan_hash, str) or canonical_sha256(unhashed_plan) != recorded_plan_hash:
        raise ValueError("geometry build plan checksum is missing or does not match its contents")

    input_snapshots = {}
    for key in ("profile", "character_recipe", "profile_schema", "recipe_schema"):
        item = plan.get("inputs", {}).get(key)
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise ValueError(f"geometry build plan is missing input record {key!r}")
        input_path = resolve_project_path(item["path"])
        if not input_path.is_file() or sha256(input_path) != item.get("sha256"):
            raise ValueError(f"geometry build plan input changed or is unavailable: {item['path']}")
        input_snapshots[key] = json.loads(input_path.read_text(encoding="utf-8"))
    reference_geometry = plan.get("inputs", {}).get("reference_geometry")
    if reference_geometry:
        source_item = reference_geometry.get("source", {})
        record_item = reference_geometry.get("calibration_record", {})
        source_path = resolve_project_path(source_item.get("path", ""))
        record_path = resolve_project_path(record_item.get("path", ""))
        if not source_path.is_file() or sha256(source_path) != source_item.get("sha256"):
            raise ValueError("geometry seed source changed or is unavailable")
        if not record_path.is_file() or sha256(record_path) != record_item.get("sha256"):
            raise ValueError("geometry seed calibration record changed or is unavailable")
        record_snapshot = json.loads(record_path.read_text(encoding="utf-8"))
        if record_snapshot != record_item.get("snapshot"):
            raise ValueError("geometry seed calibration record snapshot differs from its frozen build plan")
        calibration = plan.get("inputs", {}).get("profile", {}).get("snapshot", {}).get("reference_calibration", {})
        if calibration.get("use") != "geometry_seed" or calibration.get("source_sha256") != source_item.get("sha256"):
            raise ValueError("geometry seed input does not match the frozen design profile")
        if reference_geometry.get("review") != calibration.get("geometry_seed_review"):
            raise ValueError("geometry seed review attestation differs from the frozen design profile")
        if resolve_project_path(calibration.get("source_path", "")) != source_path:
            raise ValueError("geometry seed source path differs from the frozen design profile")
        if reference_geometry.get("selected_mesh_object") != record_snapshot.get("geometry", {}).get("selected_mesh_object"):
            raise ValueError("selected source mesh differs from the frozen calibration record")
    builder = plan.get("builder")
    compiler = plan.get("compiler")
    if not isinstance(builder, dict) or builder.get("sha256") != sha256(Path(__file__).resolve()):
        raise ValueError("geometry build plan was compiled for a different Blender builder revision")
    compiler_path = resolve_project_path(compiler.get("path", "")) if isinstance(compiler, dict) else None
    if compiler_path is None or not compiler_path.is_file() or sha256(compiler_path) != compiler.get("sha256"):
        raise ValueError("geometry build plan compiler revision is unavailable or has changed")

    profile = plan.get("build_profile")
    source_profile = plan.get("inputs", {}).get("profile", {}).get("snapshot")
    recipe = plan.get("inputs", {}).get("character_recipe", {}).get("snapshot")
    if not isinstance(profile, dict) or not isinstance(recipe, dict):
        raise ValueError("geometry build plan lacks its profile or recipe snapshots")
    if source_profile != input_snapshots["profile"] or recipe != input_snapshots["character_recipe"]:
        raise ValueError("geometry build plan snapshots do not match their hashed input files")
    expected_build_profile = load_profile(resolve_project_path(plan["inputs"]["profile"]["path"]))
    expected_build_profile["body"] = recipe["body"]
    if profile != expected_build_profile:
        raise ValueError("effective build profile does not apply exactly the frozen recipe body controls")
    if profile.get("character_id") != plan.get("character_id") or recipe.get("character_id") != plan.get("character_id"):
        raise ValueError("geometry build plan character IDs do not agree")
    if profile.get("body") != recipe.get("body") or recipe.get("pose") != DEFAULT_NEUTRAL_POSE:
        raise ValueError("geometry build plan profile does not match its recipe body and canonical T-pose")
    if plan.get("rigging", {}).get("required_for_mesh_build") is not False:
        raise ValueError("first-stage geometry build plans must not require a rig")
    return plan, profile


def normalized_reference_point(point: Vector, low: Vector, high: Vector) -> Vector:
    height = high.z - low.z
    center_x, center_y = (low.x + high.x) * 0.5, (low.y + high.y) * 0.5
    # Atlas uses +Y as front and -X for the character's left; the source rig
    # uses -Y for front and +X for its L_* joints.
    return Vector((-(point.x - center_x) / height, -(point.y - center_y) / height, (point.z - low.z) / height))


def pose_reference_arms_t_pose(
    body: bpy.types.Object,
    shoulder_left: Vector | None,
    elbow_left: Vector | None,
    wrist_left: Vector | None,
    shoulder_right: Vector | None,
    elbow_right: Vector | None,
    wrist_right: Vector | None,
) -> tuple[dict[str, tuple[Vector, Vector, object, Vector, object]], dict[str, int]]:
    """Rotate source arm/hand mesh islands from its rest pose into Atlas T-pose."""
    adjacency = [set() for _ in body.data.vertices]
    for edge in body.data.edges:
        a, b = edge.vertices
        adjacency[a].add(b)
        adjacency[b].add(a)
    visited: set[int] = set()
    islands: list[list[int]] = []
    for start in range(len(adjacency)):
        if start in visited:
            continue
        stack, island = [start], []
        visited.add(start)
        while stack:
            index = stack.pop()
            island.append(index)
            for neighbor in adjacency[index]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    stack.append(neighbor)
        islands.append(island)

    transforms: dict[str, tuple[Vector, Vector, object, Vector, object]] = {}
    posed_counts = {"left": 0, "right": 0}
    for side, shoulder, elbow, wrist, side_sign in (
        ("left", shoulder_left, elbow_left, wrist_left, -1),
        ("right", shoulder_right, elbow_right, wrist_right, 1),
    ):
        if shoulder is None or elbow is None or wrist is None:
            continue
        posed_shoulder = shoulder.copy()
        upper_axis = Vector((elbow.x - shoulder.x, 0, elbow.z - shoulder.z))
        forearm_axis = Vector((wrist.x - elbow.x, 0, wrist.z - elbow.z))
        if upper_axis.length < 1e-5 or forearm_axis.length < 1e-5:
            continue
        target_upper = Vector((side_sign * upper_axis.length, 0, 0))
        upper_rotation = upper_axis.rotation_difference(target_upper)
        posed_elbow = posed_shoulder + upper_rotation @ (elbow - shoulder)
        posed_forearm = upper_rotation @ forearm_axis
        target_forearm = Vector((side_sign * forearm_axis.length, 0, 0))
        forearm_rotation = posed_forearm.rotation_difference(target_forearm)
        transforms[side] = (shoulder.copy(), posed_shoulder, upper_rotation, posed_elbow, forearm_rotation)
        for island in islands:
            center = sum((body.data.vertices[index].co for index in island), Vector()) / len(island)
            # Select arm islands by their centroid on the correct side. Using
            # only the outer extent also selects the wide torso island and
            # rotates the chest around the shoulder, causing the visible gap.
            if center.x * side_sign < 0.14 or not 0.18 < center.z < 0.90:
                continue
            upper_length_sq = upper_axis.length_squared
            elbow_fraction = (elbow - shoulder).dot(upper_axis) / upper_length_sq
            arm_fraction = (center - shoulder).dot(upper_axis) / upper_length_sq
            upper_segment = arm_fraction <= elbow_fraction + 0.04
            for index in island:
                vertex = body.data.vertices[index]
                upper_posed = posed_shoulder + upper_rotation @ (vertex.co - shoulder)
                if upper_segment:
                    vertex.co = upper_posed
                else:
                    vertex.co = posed_elbow + forearm_rotation @ (upper_posed - posed_elbow)
            posed_counts[side] += len(island)
    body.data.update()
    return transforms, posed_counts


def transform_pose_point(point: Vector | None, transform: tuple[Vector, Vector, object, Vector, object] | None,
                         upper_segment: bool = False) -> Vector | None:
    if point is None or transform is None:
        return point.copy() if point is not None else None
    source_shoulder, posed_shoulder, upper_rotation, posed_elbow, forearm_rotation = transform
    upper_posed = posed_shoulder + upper_rotation @ (point - source_shoulder)
    if upper_segment:
        return upper_posed
    return posed_elbow + forearm_rotation @ (upper_posed - posed_elbow)


def stitch_reference_axilla_surfaces(body: bpy.types.Object) -> int:
    """Stitch torso and upper-arm boundary arcs into a blended surface patch."""
    import bmesh

    mesh = body.data
    original_count = len(mesh.vertices)
    adjacency = [set() for _ in range(original_count)]
    for edge in mesh.edges:
        a, b = edge.vertices
        if a < original_count and b < original_count:
            adjacency[a].add(b)
            adjacency[b].add(a)
    components = []
    visited = set()
    for start in range(original_count):
        if start in visited:
            continue
        stack, indices = [start], []
        visited.add(start)
        while stack:
            index = stack.pop()
            indices.append(index)
            for neighbor in adjacency[index]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    stack.append(neighbor)
        if len(indices) < 80:
            continue
        center = sum((mesh.vertices[index].co for index in indices), Vector()) / len(indices)
        components.append((indices, center))

    torso = max((item for item in components if abs(item[1].x) < 0.10 and 0.50 < item[1].z < 0.78),
                key=lambda item: len(item[0]), default=None)
    if torso is None:
        return 0

    edge_use = {tuple(sorted(edge.vertices)): 0 for edge in mesh.edges
                if edge.vertices[0] < original_count and edge.vertices[1] < original_count}
    for polygon in mesh.polygons:
        if any(index >= original_count for index in polygon.vertices):
            continue
        for offset in range(len(polygon.vertices)):
            edge = tuple(sorted((polygon.vertices[offset], polygon.vertices[(offset + 1) % len(polygon.vertices)])))
            if edge in edge_use:
                edge_use[edge] += 1

    def boundary_loop(indices: list[int]) -> list[int] | None:
        index_set = set(indices)
        links = {index: set() for index in indices}
        for (a, b), uses in edge_use.items():
            if uses == 1 and a in index_set and b in index_set:
                links[a].add(b)
                links[b].add(a)
        starts = [index for index, neighbors in links.items() if neighbors]
        if not starts or any(len(links[index]) != 2 for index in starts):
            return None
        ordered = [starts[0]]
        previous, current = -1, starts[0]
        while True:
            next_index = next(index for index in links[current] if index != previous)
            if next_index == ordered[0]:
                break
            if next_index in ordered:
                return None
            ordered.append(next_index)
            previous, current = current, next_index
        return ordered if len(ordered) == len(starts) else None

    torso_loop = boundary_loop(torso[0])
    if not torso_loop:
        return 0

    def best_arc_pair(arm_loop: list[int], side_sign: int):
        choices = []
        size = 15
        for torso_start in range(len(torso_loop)):
            for torso_direction in (1, -1):
                torso_arc = [torso_loop[(torso_start + torso_direction * step) % len(torso_loop)]
                             for step in range(size)]
                torso_points = [mesh.vertices[index].co for index in torso_arc]
                if not all(point.x * side_sign > 0.04 for point in torso_points):
                    continue
                for arm_start in range(len(arm_loop)):
                    for arm_direction in (1, -1):
                        arm_arc = [arm_loop[(arm_start + arm_direction * step) % len(arm_loop)]
                                   for step in range(size)]
                        arm_points = [mesh.vertices[index].co for index in arm_arc]
                        if not all(point.x * side_sign > 0.04 for point in arm_points):
                            continue
                        distances = [(a - b).length for a, b in zip(torso_points, arm_points)]
                        score = sum(distances) / size
                        if max(distances) <= 0.25:
                            choices.append((score, torso_arc, arm_arc))
        return min(choices, key=lambda item: item[0]) if choices else None

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    original_bm_verts = list(bm.verts)
    uv_layer = bm.loops.layers.uv.active
    vertex_uv = {}
    if uv_layer:
        uv_samples = {vert: [] for vert in original_bm_verts}
        for face in bm.faces:
            for loop in face.loops:
                uv_samples[loop.vert].append(loop[uv_layer].uv.copy())
        for vertex, samples in uv_samples.items():
            if samples:
                vertex_uv[vertex] = Vector((
                    sum(sample.x for sample in samples) / len(samples),
                    sum(sample.y for sample in samples) / len(samples),
                ))
    stitched_sides = 0
    new_faces = []
    for side_sign in (-1, 1):
        arms = [item for item in components if item is not torso and item[1].x * side_sign > 0.20
                and 0.58 < item[1].z < 0.82]
        if not arms:
            continue
        # The reference has two overlapping shoulder/upper-arm surface islands
        # on each side. The smaller island sits slightly closer to the torso,
        # but stitching it leaves the substantial upper-arm shell detached.
        # Bridge the largest island in the shoulder-height envelope; the
        # topology gate below confirms it actually joins the torso.
        upper_arm = max(arms, key=lambda item: len(item[0]))
        arm_loop = boundary_loop(upper_arm[0])
        if not arm_loop:
            continue
        pair = best_arc_pair(arm_loop, side_sign)
        if pair is None:
            continue
        _, torso_arc, arm_arc = pair
        grid = [[original_bm_verts[index] for index in torso_arc]]
        grid_uv = [[vertex_uv.get(original_bm_verts[index]) for index in torso_arc]]
        # Interpolate the existing torso surface toward the arm boundary in
        # several curved rows. UVs follow the same blend, like cloning nearby skin
        # over the full gap and feathering it into both original surfaces.
        for fraction in (0.12, 0.24, 0.38, 0.50, 0.62, 0.76, 0.88):
            row, row_uv = [], []
            for torso_index, arm_index in zip(torso_arc, arm_arc):
                a = mesh.vertices[torso_index].co
                b = mesh.vertices[arm_index].co
                point = a.lerp(b, fraction)
                blend = math.sin(math.pi * fraction)
                point.x -= side_sign * 0.008 * blend
                point.y += 0.006 * blend
                row.append(bm.verts.new(point))
                uv_a = vertex_uv.get(original_bm_verts[torso_index])
                uv_b = vertex_uv.get(original_bm_verts[arm_index])
                if uv_a is None:
                    row_uv.append(uv_b.copy() if uv_b is not None else None)
                elif uv_b is None or (uv_a - uv_b).length > 0.15:
                    # The source has independent UV islands. Clone the nearby
                    # torso skin across the bridge instead of averaging across
                    # unrelated atlas islands (which produces black wedges).
                    row_uv.append(uv_a.copy())
                else:
                    row_uv.append(uv_a.lerp(uv_b, fraction))
            grid.append(row)
            grid_uv.append(row_uv)
        grid.append([original_bm_verts[index] for index in arm_arc])
        grid_uv.append([vertex_uv.get(original_bm_verts[index]) for index in arm_arc])
        for row_index in range(len(grid) - 1):
            for col in range(len(torso_arc) - 1):
                face = bm.faces.new((grid[row_index][col], grid[row_index][col + 1],
                                     grid[row_index + 1][col + 1], grid[row_index + 1][col]))
                face.material_index = 0
                face.smooth = True
                face.normal_update()
                face_center = sum((vert.co for vert in face.verts), Vector()) / len(face.verts)
                desired_normal = Vector((float(side_sign), face_center.y * 3.0,
                                         (face_center.z - 0.72) * 1.5))
                if face.normal.dot(desired_normal) < 0:
                    face.normal_flip()
                if uv_layer:
                    for loop in face.loops:
                        for r, face_row in enumerate(grid):
                            if loop.vert in face_row:
                                c = face_row.index(loop.vert)
                                value = grid_uv[r][c]
                                if value is not None:
                                    loop[uv_layer].uv = value
                                break
                new_faces.append(face)
        stitched_sides += 1
    bm.to_mesh(body.data)
    bm.free()
    body.data.update()
    return stitched_sides


def adapt_reference_proportions(
    body: bpy.types.Object, profile: dict, landmarks: dict[str, Vector],
) -> dict[str, float]:
    """Apply supported profile proportion controls to a normalized source mesh.

    This is a deterministic, smooth spatial warp over the reviewed source mesh,
    not a retopology or a claim that arbitrary source anatomy will deform well.
    The result still requires visual and topology review.
    """
    controls = profile["body"]
    vertices = body.data.vertices
    if not vertices:
        raise RuntimeError("Reference body mesh is empty.")
    low_z = min(vertex.co.z for vertex in vertices)
    high_z = max(vertex.co.z for vertex in vertices)
    height = high_z - low_z
    if height <= 1e-6:
        raise RuntimeError("Reference body has no measurable height.")

    def fallback(name: str, z: float, x: float = 0.0) -> Vector:
        point = landmarks.get(name)
        return point.copy() if point is not None else Vector((x, 0.0, z))

    # The importer normalizes source geometry to z=0..1. Rigged sources provide
    # stronger anchors; these conservative defaults support unrigged body meshes.
    pelvis = fallback("root", low_z + height * 0.47)
    shoulder_left = fallback("shoulder_left", low_z + height * 0.78, -0.15)
    shoulder_right = fallback("shoulder_right", low_z + height * 0.78, 0.15)
    if abs(shoulder_left.x) + abs(shoulder_right.x) < 0.02:
        sample_z = low_z + height * 0.78
        sample = [abs(vertex.co.x) for vertex in vertices if abs(vertex.co.z - sample_z) <= height * 0.04]
        half = max(sample, default=0.15)
        shoulder_left = Vector((-half * 0.62, 0, sample_z))
        shoulder_right = Vector((half * 0.62, 0, sample_z))
    shoulder_z = (shoulder_left.z + shoulder_right.z) * 0.5
    shoulder_half = max(0.06, (abs(shoulder_left.x) + abs(shoulder_right.x)) * 0.5)
    knee_left = fallback("knee_left", low_z + height * 0.30, -0.07)
    knee_right = fallback("knee_right", low_z + height * 0.30, 0.07)
    if abs(knee_left.z - pelvis.z) < height * 0.05 and abs(knee_right.z - pelvis.z) < height * 0.05:
        knee_left.z = knee_right.z = low_z + height * 0.30
    ankle_left = fallback("ankle_left", low_z + height * 0.08, -0.06)
    ankle_right = fallback("ankle_right", low_z + height * 0.08, 0.06)
    if abs(ankle_left.z - pelvis.z) < height * 0.05 and abs(ankle_right.z - pelvis.z) < height * 0.05:
        ankle_left.z = ankle_right.z = low_z + height * 0.08
    wrist_left = fallback("wrist_left", shoulder_z, -shoulder_half * 1.8)
    wrist_right = fallback("wrist_right", shoulder_z, shoulder_half * 1.8)
    if abs(wrist_left.x) + abs(wrist_right.x) < shoulder_half * 0.5:
        sample_z = low_z + height * 0.77
        sample = [abs(vertex.co.x) for vertex in vertices if abs(vertex.co.z - sample_z) <= height * 0.04]
        half = max(sample, default=shoulder_half * 1.8)
        wrist_left = Vector((-half, 0, sample_z))
        wrist_right = Vector((half, 0, sample_z))
    neck = fallback("neck", low_z + height * 0.83)
    head = fallback("head", low_z + height * 0.91)
    waist_z = pelvis.z + (shoulder_z - pelvis.z) * 0.45
    thigh_z = pelvis.z + ((knee_left.z + knee_right.z) * 0.5 - pelvis.z) * 0.45

    def pulse(z: float, center: float, spread: float) -> float:
        spread = max(spread, height * 0.015)
        return math.exp(-0.5 * ((z - center) / spread) ** 2)

    def smooth01(value: float) -> float:
        value = min(1.0, max(0.0, value))
        return value * value * (3.0 - 2.0 * value)

    ratios = {name: controls[name] / 100.0 for name in (
        "build_percent", "shoulder_percent", "arm_length_percent", "leg_length_percent",
        "head_percent", "torso_length_percent", "stomach_percent", "hips_percent",
        "thighs_percent", "hand_percent", "foot_percent",
    )}
    torso_span = max(height * 0.16, shoulder_z - pelvis.z)
    leg_span = max(height * 0.16, pelvis.z - (knee_left.z + knee_right.z) * 0.5)
    head_span = max(height * 0.08, high_z - neck.z)
    transformed_landmarks: dict[str, Vector] = {}

    def transform(point: Vector) -> Vector:
        original = point.copy()
        z = original.z
        if z < pelvis.z:
            z = pelvis.z + (z - pelvis.z) * ratios["leg_length_percent"]
        elif z <= shoulder_z:
            z = pelvis.z + (z - pelvis.z) * ratios["torso_length_percent"]
        else:
            z = pelvis.z + torso_span * ratios["torso_length_percent"] + (z - shoulder_z)

        x = original.x * ratios["build_percent"]
        y = original.y * ratios["build_percent"]
        torso_weight = math.exp(-0.5 * (abs(original.x) / max(shoulder_half * 1.25, 0.08)) ** 2)
        section_factor = 1.0
        section_factor *= 1.0 + (ratios["shoulder_percent"] - 1.0) * pulse(original.z, shoulder_z, torso_span * 0.22) * torso_weight
        section_factor *= 1.0 + (ratios["stomach_percent"] - 1.0) * pulse(original.z, waist_z, torso_span * 0.18) * torso_weight
        section_factor *= 1.0 + (ratios["hips_percent"] - 1.0) * pulse(original.z, pelvis.z, torso_span * 0.20) * torso_weight
        section_factor *= 1.0 + (ratios["thighs_percent"] - 1.0) * pulse(original.z, thigh_z, leg_span * 0.24)
        x *= section_factor
        y *= section_factor

        arm_weight = pulse(original.z, shoulder_z, height * 0.075)
        for wrist in (wrist_left, wrist_right):
            if abs(original.x) > shoulder_half * 0.95:
                distance = abs(original.x - math.copysign(shoulder_half, original.x))
                arm_weight = max(arm_weight, pulse(original.z, wrist.z, height * 0.07) * smooth01(distance / max(abs(wrist.x) - shoulder_half, 0.05)))
        if arm_weight > 0:
            x *= 1.0 + (ratios["arm_length_percent"] - 1.0) * arm_weight

        # Scale the head and extremities around their source landmarks so their
        # relative placement follows the warped torso and limb lengths.
        head_weight = smooth01((original.z - neck.z) / head_span)
        mapped_head_center = Vector((head.x * ratios["build_percent"], head.y * ratios["build_percent"],
                                     pelvis.z + torso_span * ratios["torso_length_percent"] + (head.z - shoulder_z)))
        point = Vector((x, y, z))
        point = mapped_head_center + (point - mapped_head_center) * (1.0 + (ratios["head_percent"] - 1.0) * head_weight)

        for wrist in (wrist_left, wrist_right):
            wrist_center = Vector((wrist.x * ratios["build_percent"], wrist.y * ratios["build_percent"],
                                   pelvis.z + (wrist.z - pelvis.z) * ratios["torso_length_percent"]))
            hand_weight = pulse(original.z, wrist.z, height * 0.055) * smooth01((abs(original.x) - shoulder_half * 0.70) / max(height * 0.08, 0.01))
            point = wrist_center + (point - wrist_center) * (1.0 + (ratios["hand_percent"] - 1.0) * hand_weight)
        for ankle in (ankle_left, ankle_right):
            ankle_center = Vector((ankle.x * ratios["build_percent"], ankle.y * ratios["build_percent"],
                                   pelvis.z + (ankle.z - pelvis.z) * ratios["leg_length_percent"]))
            foot_weight = pulse(original.z, ankle.z - height * 0.015, height * 0.045) * smooth01((height * 0.09 - (original - ankle).length) / max(height * 0.05, 0.01))
            point = ankle_center + (point - ankle_center) * (1.0 + (ratios["foot_percent"] - 1.0) * foot_weight)
        return point

    for vertex in vertices:
        vertex.co = transform(vertex.co)
    for name, point in landmarks.items():
        transformed_landmarks[name] = transform(point)
    body.data.update()
    landmarks.clear()
    landmarks.update(transformed_landmarks)
    body["atlas.source_profile_adaptations"] = json.dumps(ratios, sort_keys=True)
    return ratios


def import_reference_body(path: Path, target_height: float, source_object_name: str, profile: dict) -> tuple[bpy.types.Object, dict[str, Vector], dict[str, float], int]:
    path = path.expanduser().resolve(strict=True)
    if path.suffix.lower() == ".glb":
        bpy.ops.import_scene.gltf(filepath=str(path))
    elif path.suffix.lower() == ".blend":
        # Geometry is loaded from the reviewed project source itself. The
        # named object in its calibration record prevents accidentally using
        # another mesh from a multi-asset Blender library.
        bpy.ops.wm.open_mainfile(filepath=str(path))
    else:
        raise RuntimeError("Reference geometry must be a .glb or .blend file.")
    depsgraph = bpy.context.evaluated_depsgraph_get()
    source = bpy.data.objects.get(source_object_name)
    if source is None or source.type != "MESH":
        raise RuntimeError(f"Calibrated source mesh {source_object_name!r} is missing from {path}")
    if len(source.data.vertices) < 100:
        raise RuntimeError(f"Calibrated source mesh is too small to use as a body: {source_object_name!r}")
    evaluated = source.evaluated_get(depsgraph)
    points = [evaluated.matrix_world @ vertex.co for vertex in evaluated.data.vertices]
    low = Vector(tuple(min(point[axis] for point in points) for axis in range(3)))
    high = Vector(tuple(max(point[axis] for point in points) for axis in range(3)))
    height = high.z - low.z
    if height <= 1e-6:
        raise RuntimeError("Reference model mesh has no vertical extent.")

    baked_mesh = bpy.data.meshes.new_from_object(evaluated, preserve_all_data_layers=True, depsgraph=depsgraph)
    for material in source.data.materials:
        if material and material.name not in {item.name for item in baked_mesh.materials if item}:
            baked_mesh.materials.append(material)
    body = bpy.data.objects.new("ATLAS_PROCEDURAL_BODY_V1", baked_mesh)
    bpy.context.scene.collection.objects.link(body)
    # Bake evaluated world coordinates into a normalized, centered, Z-up mesh.
    center_x, center_y = (low.x + high.x) * 0.5, (low.y + high.y) * 0.5
    scale = 1.0 / height
    for vertex in body.data.vertices:
        point = evaluated.matrix_world @ vertex.co
        vertex.co = normalized_reference_point(point, low, high)
    # The X+Y reflection is a 180-degree rotation with positive determinant,
    # so source winding remains valid. Preserve source face winding and split
    # normals; recalculation across disconnected/open islands can invert faces.
    body.data.update()
    for polygon in body.data.polygons:
        polygon.use_smooth = True
    # The reference is assembled from multiple open surface islands. Exporting
    # the material as single-sided makes inward-facing palms/chest patches look
    # like missing geometry in real-time viewers even though the faces exist.
    for material in body.data.materials:
        if material:
            material.use_backface_culling = False

    armatures = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    rig = max(armatures, key=lambda obj: len(obj.data.bones)) if armatures else None
    bones = {bone.name.lower(): bone for bone in rig.data.bones} if rig else {}

    def bone_point(*tokens: str, tail: bool = False) -> Vector | None:
        found = next((bone for name, bone in bones.items() if any(token in name for token in tokens)), None)
        if not found:
            return None
        coordinate = found.tail_local if tail else found.head_local
        return normalized_reference_point(rig.matrix_world @ coordinate, low, high)

    def average(first: Vector | None, second: Vector | None, fallback: Vector) -> Vector:
        if first is None:
            return second.copy() if second is not None else fallback.copy()
        if second is None:
            return first.copy()
        return (first + second) * 0.5

    center = Vector((0.0, 0.0, 0.5))
    pelvis = bone_point("hips", "pelvis") or Vector((0, 0, 0.41))
    spine = bone_point("spine") or (pelvis + Vector((0, 0, 0.10)))
    chest = bone_point("chest") or (pelvis + Vector((0, 0, 0.25)))
    neck = bone_point("neck") or (chest + Vector((0, 0, 0.12)))
    head = bone_point("head") or (neck + Vector((0, 0, 0.08)))
    shoulder_l, shoulder_r = bone_point("l_shoulder", "left_shoulder"), bone_point("r_shoulder", "right_shoulder")
    elbow_l, elbow_r = bone_point("l_elbow", "left_elbow"), bone_point("r_elbow", "right_elbow")
    wrist_l, wrist_r = bone_point("l_wrist", "left_wrist"), bone_point("r_wrist", "right_wrist")
    hand_l = bone_point("l_finger", "left_finger", tail=True) or wrist_l
    hand_r = bone_point("r_finger", "right_finger", tail=True) or wrist_r
    pose_transforms, posed_vertices = pose_reference_arms_t_pose(
        body, shoulder_l, elbow_l, wrist_l, shoulder_r, elbow_r, wrist_r,
    )
    shoulder_l = transform_pose_point(shoulder_l, pose_transforms.get("left"), upper_segment=True)
    elbow_l = transform_pose_point(elbow_l, pose_transforms.get("left"), upper_segment=True)
    wrist_l = transform_pose_point(wrist_l, pose_transforms.get("left"))
    hand_l = transform_pose_point(hand_l, pose_transforms.get("left"))
    shoulder_r = transform_pose_point(shoulder_r, pose_transforms.get("right"), upper_segment=True)
    elbow_r = transform_pose_point(elbow_r, pose_transforms.get("right"), upper_segment=True)
    wrist_r = transform_pose_point(wrist_r, pose_transforms.get("right"))
    hand_r = transform_pose_point(hand_r, pose_transforms.get("right"))
    axilla_fill_count = stitch_reference_axilla_surfaces(body)
    knee_l, knee_r = bone_point("l_knee", "left_knee"), bone_point("r_knee", "right_knee")
    ankle_l, ankle_r = bone_point("l_ankle", "left_ankle"), bone_point("r_ankle", "right_ankle")
    eye_l, eye_r = bone_point("l_eye", "left_eye"), bone_point("r_eye", "right_eye")
    eye_mid = average(eye_l, eye_r, head + Vector((0, 0.045, 0.015)))
    landmarks = {
        "root": pelvis.copy(), "spine_lower": spine.copy(), "spine_upper": chest.copy(),
        "neck": neck.copy(), "head": head.copy(), "crown": Vector((0, 0, 1.0)),
        "collarbone_left": shoulder_l or chest.copy(), "collarbone_right": shoulder_r or chest.copy(),
        "eye_left": eye_l or (eye_mid + Vector((-0.045, 0, 0))),
        "eye_right": eye_r or (eye_mid + Vector((0.045, 0, 0))),
        "eyebrow_left": (eye_l or eye_mid) + Vector((0, 0, 0.025)),
        "eyebrow_right": (eye_r or eye_mid) + Vector((0, 0, 0.025)),
        "nose": eye_mid + Vector((0, 0.035, -0.035)),
        "shoulder_left": shoulder_l or chest.copy(), "elbow_left": elbow_l or chest.copy(),
        "wrist_left": wrist_l or chest.copy(), "hand_left": hand_l or chest.copy(),
        "shoulder_right": shoulder_r or chest.copy(), "elbow_right": elbow_r or chest.copy(),
        "wrist_right": wrist_r or chest.copy(), "hand_right": hand_r or chest.copy(),
        "hip_left": bone_point("hips", "pelvis") or pelvis.copy(), "knee_left": knee_l or pelvis.copy(),
        "ankle_left": ankle_l or pelvis.copy(), "hip_right": bone_point("hips", "pelvis") or pelvis.copy(),
        "knee_right": knee_r or pelvis.copy(), "ankle_right": ankle_r or pelvis.copy(),
    }
    source_adaptations = adapt_reference_proportions(body, profile, landmarks)
    landmarks = project_surface_landmarks(body, landmarks)

    # Keep only the baked visible mesh; imported armatures/helper objects never
    # enter the Atlas file or preview.
    for obj in list(bpy.context.scene.objects):
        if obj != body:
            bpy.data.objects.remove(obj, do_unlink=True)
    body.name = "ATLAS_PROCEDURAL_BODY_V1"
    body.data.name = "ATLAS_PROCEDURAL_BODY_V1_MESH"
    body["atlas.source_mode"] = "licensed_reference_mesh_seed"
    body["atlas.source_file"] = path.name
    body["atlas.source_sha256"] = sha256(path)
    body["atlas.mesh_object_count"] = 1
    body["atlas.body_topology"] = "baked_reference_mesh_single_object_with_source_component_islands"
    body["atlas.source_original_height"] = height
    body["atlas.source_to_target_scale"] = target_height * scale
    body["atlas.neutral_pose"] = DEFAULT_NEUTRAL_POSE
    body["atlas.t_pose_arm_vertices_left"] = posed_vertices["left"]
    body["atlas.t_pose_arm_vertices_right"] = posed_vertices["right"]
    body["atlas.axilla_stitched_sides"] = axilla_fill_count
    body["atlas.source_profile_adaptations"] = json.dumps(source_adaptations, sort_keys=True)
    dimension_profile = {"body": {
        "build_percent": 100, "shoulder_percent": 100, "torso_length_percent": 100,
        "head_percent": 100, "arm_length_percent": 100, "leg_length_percent": 100,
        "hips_percent": 100, "stomach_percent": 100, "bust_percent": 100,
        "thighs_percent": 100, "glutes_percent": 100, "jaw_percent": 100,
        "hand_percent": 100, "foot_percent": 100, "ear_percent": 100,
        "muscle_percent": 100, "nose_percent": 100,
    }, "concept": {"archetype": "humanoid"}}
    dimensions = build_dimensions(dimension_profile)
    dimensions.update({
        "pelvis_z": landmarks["root"].z,
        "ankle_z": average(landmarks["ankle_left"], landmarks["ankle_right"], Vector((0, 0, 0.06))).z,
        "knee_z": average(landmarks["knee_left"], landmarks["knee_right"], Vector((0, 0, 0.3))).z,
        "wrist_z": average(landmarks["wrist_left"], landmarks["wrist_right"], Vector((0, 0, 0.5))).z,
        "shoulder_z": average(landmarks["shoulder_left"], landmarks["shoulder_right"], chest).z,
        "neck_z": landmarks["neck"].z,
        "head_z": landmarks["head"].z,
        "waist_z": landmarks["root"].z + (landmarks["shoulder_left"].z - landmarks["root"].z) * 0.45,
        "chest_z": landmarks["root"].z + (landmarks["shoulder_left"].z - landmarks["root"].z) * 0.75,
        "shoulder_half": max(0.01, abs(landmarks["shoulder_left"].x), abs(landmarks["shoulder_right"].x)),
        "wrist_half": max(0.01, abs(landmarks["wrist_left"].x), abs(landmarks["wrist_right"].x)),
        "hip_half": max(0.01, abs(landmarks["hip_left"].x), abs(landmarks["hip_right"].x)),
        "head": profile["body"]["head_percent"] / 100,
        "ear": profile["body"]["ear_percent"] / 100,
        "jaw": profile["body"]["jaw_percent"] / 100,
        "nose": profile["body"]["nose_percent"] / 100,
    })
    head_vertices = [vertex.co for vertex in body.data.vertices if vertex.co.z >= landmarks["neck"].z]
    if head_vertices:
        dimensions["head_rx"] = max(abs(point.x - landmarks["head"].x) for point in head_vertices)
        dimensions["head_ry"] = max(abs(point.y - landmarks["head"].y) for point in head_vertices)
        dimensions["head_rz"] = max(
            abs(point.z - landmarks["head"].z) for point in head_vertices
        )
    components = connected_component_sizes(body.data)
    return body, landmarks, dimensions, components


def srgb_hex_to_linear(color: str) -> tuple[float, float, float, float]:
    values = [int(color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in values]
    return (*linear, 1.0)


def make_material(name: str, color: str, roughness: float = 0.78) -> bpy.types.Material:
    rgba = srgb_hex_to_linear(color)
    material = bpy.data.materials.new(name)
    material.diffuse_color = rgba
    material.use_nodes = True
    shader = material.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = rgba
    shader.inputs["Roughness"].default_value = roughness
    return material


def add_ellipsoid(data: bpy.types.MetaBall, center: tuple[float, float, float],
                  radii: tuple[float, float, float], rotation: tuple[float, float, float] = (0, 0, 0)) -> None:
    element = data.elements.new()
    element.type = "ELLIPSOID"
    element.co = center
    element.radius = 1.0
    element.size_x, element.size_y, element.size_z = radii
    element.rotation = Euler(rotation).to_quaternion()
    element.stiffness = 2.0


def add_limb(data: bpy.types.MetaBall, start: Vector, end: Vector, radius: float, depth_scale: float = 1.0) -> None:
    direction = end - start
    if direction.length < 1e-5:
        raise ValueError("Generated limb has zero length")
    orientation = direction.to_track_quat("Z", "Y").to_euler()
    midpoint = (start + end) * 0.5
    # Metaball capsule ends need a deliberate overlap at joints. The former
    # 0.78 radius extension left visible gaps at shoulders, elbows, wrists,
    # hips, and knees under the production threshold.
    half_length = direction.length * 0.5 + radius * 1.55
    add_ellipsoid(data, tuple(midpoint), (radius, radius * depth_scale, half_length), tuple(orientation))


def add_torso_profile(data: bpy.types.MetaBall, d: dict[str, float]) -> None:
    """Build a continuous torso from closely spaced, interpolated sections."""
    build, torso, shoulder = d["build"], d["torso"], d["shoulder"]
    muscle = d["muscle"]
    stations = [
        (d["pelvis_z"] - 0.13, 0.105 * d["hip"] * build, 0.094 * build),
        (d["pelvis_z"] - 0.055, 0.140 * d["hip"] * build, 0.116 * build * d["glute"]),
        (d["pelvis_z"], 0.145 * d["hip"] * build, 0.122 * build * d["glute"]),
        (d["waist_z"], 0.132 * build * d["stomach"], 0.108 * build * d["stomach"]),
        ((d["waist_z"] + d["chest_z"]) * 0.5,
         0.145 * build * (0.92 + 0.08 * muscle), 0.108 * build),
        (d["chest_z"], 0.174 * shoulder * build * (0.92 + 0.08 * muscle),
         0.118 * build * (0.72 + 0.28 * d["bust"])),
        (d["chest_z"] + (d["shoulder_z"] - d["chest_z"]) * 0.55,
         0.158 * shoulder * build, 0.104 * build),
        (d["shoulder_z"], 0.140 * shoulder * build, 0.090 * build),
        (d["shoulder_z"] + 0.055, 0.108 * shoulder * build, 0.073 * build),
    ]
    for first, second in zip(stations, stations[1:]):
        z0, x0, y0 = first
        z1, x1, y1 = second
        steps = max(2, math.ceil((z1 - z0) / 0.035))
        for index in range(steps):
            t = index / steps
            smooth_t = t * t * (3.0 - 2.0 * t)
            z = z0 + (z1 - z0) * t
            rx = x0 + (x1 - x0) * smooth_t
            ry = y0 + (y1 - y0) * smooth_t
            add_ellipsoid(data, (0, 0, z), (rx, ry, 0.060 * torso))
    z, rx, ry = stations[-1]
    add_ellipsoid(data, (0, 0, z), (rx, ry, 0.060 * torso))


def build_dimensions(profile: dict) -> dict[str, float]:
    body = profile["body"]
    build = body["build_percent"] / 100
    shoulder = body["shoulder_percent"] / 100
    priors = ARCHETYPE_PRIORS[profile["concept"]["archetype"]]
    torso = body["torso_length_percent"] / 100
    head = body["head_percent"] / 100 * priors["head"]
    arm = body["arm_length_percent"] / 100
    leg = body["leg_length_percent"] / 100
    hip = body["hips_percent"] / 100
    stomach = body["stomach_percent"] / 100
    bust = body["bust_percent"] / 100
    thigh = body["thighs_percent"] / 100
    glute = body["glutes_percent"] / 100
    jaw = body["jaw_percent"] / 100 * priors["jaw"]
    hand = body["hand_percent"] / 100 * priors["hand"]
    foot = body["foot_percent"] / 100 * priors["foot"]
    ear = body["ear_percent"] / 100 * priors["ear"]
    muscle = body["muscle_percent"] / 100
    nose = body["nose_percent"] / 100 * priors["nose"]

    pelvis_z = 0.84
    waist_z = pelvis_z + 0.17 * torso
    chest_z = pelvis_z + 0.39 * torso
    shoulder_z = pelvis_z + 0.56 * torso
    neck_z = shoulder_z + 0.075
    head_z = neck_z + 0.135
    # A consistent T-pose is the neutral authoring pose for marker placement.
    elbow_z = shoulder_z
    wrist_z = shoulder_z
    head_rx, head_ry, head_rz = 0.083 * head, 0.092 * head, 0.112 * head
    shoulder_half = 0.155 * shoulder * build
    elbow_half = shoulder_half + 0.12 * arm
    wrist_half = shoulder_half + 0.215 * arm
    hand_half = wrist_half + 0.080 * arm
    hip_half = 0.104 * hip * build
    knee_z = pelvis_z - 0.39 * leg
    ankle_z = pelvis_z - 0.78 * leg
    foot_z = max(0.035, ankle_z - 0.015)
    foot_forward = 0.055

    return {
        "build": build, "shoulder": shoulder, "torso": torso, "head": head,
        "arm": arm, "leg": leg, "hip": hip, "stomach": stomach,
        "bust": bust, "thigh": thigh, "glute": glute,
        "jaw": jaw, "hand": hand, "foot": foot, "ear": ear,
        "muscle": muscle, "nose": nose,
        "pelvis_z": pelvis_z, "waist_z": waist_z, "chest_z": chest_z,
        "shoulder_z": shoulder_z, "neck_z": neck_z, "head_z": head_z,
        "elbow_z": elbow_z, "wrist_z": wrist_z,
        "head_rx": head_rx, "head_ry": head_ry, "head_rz": head_rz,
        "shoulder_half": shoulder_half, "elbow_half": elbow_half,
        "wrist_half": wrist_half, "hand_half": hand_half, "hip_half": hip_half,
        "knee_z": knee_z, "ankle_z": ankle_z, "foot_z": foot_z,
        "foot_forward": foot_forward,
    }


def build_landmarks(dimensions: dict[str, float]) -> dict[str, Vector]:
    d = dimensions
    head_center = Vector((0, 0, d["head_z"]))
    eye_z = d["head_z"] + 0.005 * d["head"]
    eye_y = d["head_ry"] * 0.88
    shoulder_z = d["shoulder_z"]
    elbow_z = shoulder_z
    wrist_z = shoulder_z
    hip_z = d["pelvis_z"]
    return {
        "root": Vector((0, 0, hip_z)),
        "spine_lower": Vector((0, 0, d["waist_z"] - 0.04)),
        "spine_upper": Vector((0, 0, d["chest_z"])),
        "neck": Vector((0, 0, d["neck_z"])),
        "head": head_center,
        "crown": Vector((0, 0, d["head_z"] + d["head_rz"])),
        "collarbone_left": Vector((-d["shoulder_half"] * 0.62, 0.085 * d["build"], d["shoulder_z"] + 0.012)),
        "collarbone_right": Vector((d["shoulder_half"] * 0.62, 0.085 * d["build"], d["shoulder_z"] + 0.012)),
        "eye_left": Vector((-d["head_rx"] * 0.39, eye_y, eye_z)),
        "eye_right": Vector((d["head_rx"] * 0.39, eye_y, eye_z)),
        "eyebrow_left": Vector((-d["head_rx"] * 0.39, eye_y * 0.95, eye_z + 0.024 * d["head"])),
        "eyebrow_right": Vector((d["head_rx"] * 0.39, eye_y * 0.95, eye_z + 0.024 * d["head"])),
        "nose": Vector((0, d["head_ry"] * (1.02 + 0.30 * d["nose"]), eye_z - 0.022 * d["head"])),
        "shoulder_left": Vector((-d["shoulder_half"] * 0.82, 0, shoulder_z - 0.015)),
        "elbow_left": Vector((-d["elbow_half"], 0, elbow_z)),
        "wrist_left": Vector((-d["wrist_half"], 0, wrist_z)),
        "hand_left": Vector((-d["hand_half"], 0, wrist_z)),
        "shoulder_right": Vector((d["shoulder_half"] * 0.82, 0, shoulder_z - 0.015)),
        "elbow_right": Vector((d["elbow_half"], 0, elbow_z)),
        "wrist_right": Vector((d["wrist_half"], 0, wrist_z)),
        "hand_right": Vector((d["hand_half"], 0, wrist_z)),
        "hip_left": Vector((-d["hip_half"], 0, hip_z - 0.02)),
        "knee_left": Vector((-d["hip_half"] * 1.13, 0, d["knee_z"])),
        "ankle_left": Vector((-d["hip_half"] * 1.10, 0, d["ankle_z"])),
        "hip_right": Vector((d["hip_half"], 0, hip_z - 0.02)),
        "knee_right": Vector((d["hip_half"] * 1.13, 0, d["knee_z"])),
        "ankle_right": Vector((d["hip_half"] * 1.10, 0, d["ankle_z"])),
    }


def project_surface_landmarks(body: bpy.types.Object, landmarks: dict[str, Vector]) -> dict[str, Vector]:
    surface_names = {
        "crown", "collarbone_left", "collarbone_right", "eye_left", "eye_right",
        "eyebrow_left", "eyebrow_right", "nose",
    }
    mesh = body.data
    mesh.calc_loop_triangles()
    triangles = [tuple(triangle.vertices) for triangle in mesh.loop_triangles]
    tree = BVHTree.FromPolygons([vertex.co for vertex in mesh.vertices], triangles, all_triangles=True)
    result = dict(landmarks)
    for name in surface_names:
        nearest = tree.find_nearest(landmarks[name])
        if nearest is None:
            raise RuntimeError(f"Could not project surface landmark {name} onto the generated base")
        result[name] = nearest[0]
    return result


def create_body(profile: dict, d: dict[str, float]) -> bpy.types.Object:
    data = bpy.data.metaballs.new("ATLAS_PARAMETRIC_BODY_FIELD")
    data.resolution = {
        "realistic": 0.006,
        "painted": 0.008,
        "stylized": 0.012,
        "low_poly": 0.035,
    }[profile["style"]]
    data.render_resolution = data.resolution
    data.threshold = 0.48
    meta = bpy.data.objects.new("ATLAS_PARAMETRIC_BODY_FIELD", data)
    bpy.context.scene.collection.objects.link(meta)

    build = d["build"]
    shoulder_z = d["shoulder_z"]
    add_torso_profile(data, d)
    add_ellipsoid(data, (0, 0, d["neck_z"]), (0.066 * build, 0.064 * build, 0.12))
    add_ellipsoid(data, (0, 0, d["head_z"]), (d["head_rx"], d["head_ry"], d["head_rz"]))
    # Jaw and chin are fused into the face volume to create a legible lower
    # face silhouette; their scale is exposed in the compact design profile.
    add_ellipsoid(data, (0, d["head_ry"] * 0.10, d["head_z"] - 0.050 * d["head"]),
                  (d["head_rx"] * 0.70 * d["jaw"], d["head_ry"] * 0.78,
                   d["head_rz"] * 0.42))
    # Nose bridge and tip are fused into the head surface.
    nose = d["nose"]
    add_ellipsoid(data, (0, d["head_ry"] * 0.76, d["head_z"] - 0.006 * d["head"]),
                  (0.022 * d["head"] * nose, 0.042 * d["head"] * nose, 0.050 * d["head"]))
    add_ellipsoid(data, (0, d["head_ry"] * 1.02, d["head_z"] - 0.026 * d["head"]),
                  (0.031 * d["head"] * nose, 0.044 * d["head"] * nose, 0.026 * d["head"]))
    # Trolls and orcs need a readable mid-face silhouette. This muzzle volume
    # blends into the nose bridge, cheeks, and jaw instead of sitting as a prop.
    if profile["concept"]["archetype"] in {"troll", "orc", "goblin"}:
        muzzle_scale = {"troll": 1.0, "orc": 0.88, "goblin": 0.72}[profile["concept"]["archetype"]]
        add_ellipsoid(data,
                      (0, d["head_ry"] * 0.63, d["head_z"] - 0.044 * d["head"]),
                      (0.054 * d["head"] * nose * muzzle_scale,
                       0.056 * d["head"] * nose * muzzle_scale,
                       0.040 * d["head"] * muzzle_scale))
    if profile["traits"]["pointed_ears"]:
        for sign in (-1, 1):
            add_ellipsoid(data,
                          (sign * d["head_rx"] * 0.80, -0.004 * d["head"],
                           d["head_z"] - 0.014 * d["head"]),
                          (0.042 * d["head"] * d["ear"],
                           0.030 * d["head"], 0.036 * d["head"]))
    # Subtle orbital and cheek planes keep the face from reading as a featureless
    # sphere while preserving a clean, deformable base surface.
    for sign in (-1, 1):
        add_ellipsoid(data,
                      (sign * d["head_rx"] * 0.39, d["head_ry"] * 0.60,
                       d["head_z"] + 0.018 * d["head"]),
                      (0.030 * d["head"], 0.040 * d["head"], 0.014 * d["head"]))
        add_ellipsoid(data,
                      (sign * d["head_rx"] * 0.43, d["head_ry"] * 0.59,
                       d["head_z"] - 0.032 * d["head"]),
                      (0.036 * d["head"], 0.024 * d["head"], 0.030 * d["head"]))

    landmarks = build_landmarks(d)
    for side in ("left", "right"):
        shoulder_point = landmarks[f"shoulder_{side}"]
        elbow = landmarks[f"elbow_{side}"]
        wrist = landmarks[f"wrist_{side}"]
        hand = landmarks[f"hand_{side}"]
        # Deltoid cap overlaps both the thorax and upper arm so the shoulder
        # silhouette reads as one continuous anatomical surface.
        sign = -1 if side == "left" else 1
        shoulder_center = Vector((sign * d["shoulder_half"] * 0.82, 0,
                                  d["shoulder_z"] - 0.025))
        add_ellipsoid(data, tuple(shoulder_center),
                      (0.092 * build * d["shoulder"], 0.092 * build,
                       0.105 * build))
        arm_radius = 0.058 * build
        forearm_radius = 0.047 * build
        add_limb(data, shoulder_point, elbow, arm_radius, 0.92)
        add_limb(data, elbow, wrist, forearm_radius, 0.88)
        palm_rx = 0.070 * build * d["hand"]
        palm_ry = 0.052 * build * d["hand"]
        add_ellipsoid(data, tuple(hand), (palm_rx, palm_ry, 0.058 * build * d["hand"]))
        # Fingers continue the wrist-to-palm axis, with a small visible gap
        # between digits for clearer rig marker and weight authoring.
        finger_radius = 0.0105 * build * d["hand"]
        hand_axis = hand - wrist
        if hand_axis.length < 1e-5:
            hand_axis = Vector((1 if side == "right" else -1, 0, -0.25))
        hand_axis.normalize()
        spread_axis = Vector((0, 0, 1))
        for finger_index in range(4):
            spread = (finger_index - 1.5) * 0.022 * build * d["hand"]
            finger_start = hand - hand_axis * 0.036 + spread_axis * spread + Vector((0, palm_ry * 0.22, 0))
            finger_length = (0.060 - finger_index * 0.004) * build * d["hand"]
            finger_end = finger_start + hand_axis * finger_length
            finger_end += spread_axis * ((finger_index - 1.5) * 0.004 * build)
            add_limb(data, finger_start, finger_end,
                     finger_radius * (1.0 - finger_index * 0.045), 0.86)
        sign = 1 if side == "right" else -1
        thumb_start = hand - hand_axis * 0.025 + Vector((-sign * palm_rx * 0.42, palm_ry * 0.30, 0.018 * build))
        thumb_end = thumb_start + Vector((-sign * 0.040 * build * d["hand"],
                                          0.020 * build, 0.020 * build * d["hand"]))
        add_limb(data, thumb_start, thumb_end, finger_radius * 1.18, 0.9)

        hip_point = landmarks[f"hip_{side}"]
        knee = landmarks[f"knee_{side}"]
        ankle = landmarks[f"ankle_{side}"]
        thigh_radius = 0.092 * build * d["thigh"]
        calf_radius = 0.064 * build
        add_limb(data, hip_point, knee, thigh_radius, 0.95)
        add_limb(data, knee, ankle, calf_radius, 0.9)
        foot_length = 0.14 * build * d["foot"]
        add_ellipsoid(data, (ankle.x, d["foot_forward"] + foot_length * 0.12, d["foot_z"]),
                      (0.071 * build * d["foot"], foot_length, 0.045 * build * d["foot"]))
        toe_center = Vector((ankle.x, d["foot_forward"] + foot_length * 0.63, d["foot_z"] - 0.004))
        add_ellipsoid(data, tuple(toe_center),
                      (0.060 * build * d["foot"], foot_length * 0.48, 0.033 * build * d["foot"]))

    bpy.ops.object.select_all(action="DESELECT")
    meta.select_set(True)
    bpy.context.view_layer.objects.active = meta
    bpy.ops.object.convert(target="MESH")
    body = bpy.context.object
    body.name = "ATLAS_PROCEDURAL_BODY_V1"
    body.data.name = "ATLAS_PROCEDURAL_BODY_V1_MESH"
    body.data.materials.append(make_material("Atlas Generated Primary Skin", profile["palette"]["skin"]))
    for polygon in body.data.polygons:
        polygon.use_smooth = profile["style"] != "low_poly"
    body["atlas.generator"] = GENERATOR_VERSION
    body["atlas.profile_archetype"] = profile["concept"]["archetype"]
    body["atlas.body_regions"] = "generated_continuous_surface"
    return body


def connected_component_sizes(mesh: bpy.types.Mesh) -> list[int]:
    adjacency = [set() for _ in mesh.vertices]
    for edge in mesh.edges:
        a, b = edge.vertices
        adjacency[a].add(b)
        adjacency[b].add(a)
    visited: set[int] = set()
    sizes = []
    for start in range(len(adjacency)):
        if start in visited:
            continue
        stack = [start]
        visited.add(start)
        size = 0
        while stack:
            vertex = stack.pop()
            size += 1
            for neighbor in adjacency[vertex]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    stack.append(neighbor)
        sizes.append(size)
    return sorted(sizes, reverse=True)


def validate_anatomical_connectivity(body: bpy.types.Object) -> list[int]:
    components = connected_component_sizes(body.data)
    if len(components) != 1:
        adjacency = [set() for _ in body.data.vertices]
        for edge in body.data.edges:
            a, b = edge.vertices
            adjacency[a].add(b)
            adjacency[b].add(a)
        visited: set[int] = set()
        bounds = []
        for start in range(len(adjacency)):
            if start in visited:
                continue
            stack = [start]
            visited.add(start)
            indices = []
            while stack:
                index = stack.pop()
                indices.append(index)
                for neighbor in adjacency[index]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        stack.append(neighbor)
            coords = [body.data.vertices[index].co for index in indices]
            bounds.append({
                "vertices": len(indices),
                "min": [round(min(v[axis] for v in coords), 3) for axis in range(3)],
                "max": [round(max(v[axis] for v in coords), 3) for axis in range(3)],
            })
        raise RuntimeError(
            "Generated anatomical surface is disconnected before facial details "
            f"are added ({len(components)} components; bounds: {bounds}). "
            "Refusing to save a broken character base."
        )
    return components


def add_cone(name: str, center: Vector, radius: float, depth: float,
             material: bpy.types.Material, rotation: tuple[float, float, float] = (0, 0, 0),
             vertices: int = 10) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cone_add(vertices=vertices, radius1=radius, radius2=0, depth=depth,
                                    end_fill_type="NGON", location=center, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name + "_MESH"
    obj.data.materials.append(material)
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    return obj


def add_sphere(name: str, center: Vector, radius: float, material: bpy.types.Material,
               scale: tuple[float, float, float] = (1, 1, 1)) -> bpy.types.Object:
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=10, radius=radius, location=center)
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name + "_MESH"
    obj.scale = scale
    obj.data.materials.append(material)
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    return obj


def add_mouth_line(head_dimensions: dict[str, float], material: bpy.types.Material) -> bpy.types.Object:
    """Create a restrained curved mouth crease that follows the front face."""
    curve_data = bpy.data.curves.new("ATLAS_FEATURE_MOUTH_CURVE", type="CURVE")
    curve_data.dimensions = "3D"
    curve_data.resolution_u = 16
    curve_data.bevel_depth = 0.0022 * head_dimensions["head"]
    curve_data.bevel_resolution = 3
    curve_data.use_fill_caps = True
    spline = curve_data.splines.new("BEZIER")
    offsets = [(-0.060, 0.000, 0.000), (-0.030, 0.006, -0.004),
               (0.0, 0.008, -0.005), (0.030, 0.006, -0.004),
               (0.060, 0.000, 0.000)]
    spline.bezier_points.add(len(offsets) - 1)
    for point, (x, y_offset, z_offset) in zip(spline.bezier_points, offsets):
        point.co = (x * head_dimensions["head"],
                    head_dimensions["head_ry"] * 0.97 + y_offset * head_dimensions["head"],
                    head_dimensions["head_z"] - 0.047 * head_dimensions["head"] + z_offset * head_dimensions["head"])
        point.handle_left_type = "AUTO"
        point.handle_right_type = "AUTO"
    obj = bpy.data.objects.new("ATLAS_FEATURE_MOUTH", curve_data)
    bpy.context.scene.collection.objects.link(obj)
    obj.data.materials.append(material)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.convert(target="MESH")
    obj = bpy.context.object
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    return obj


def create_features(profile: dict, d: dict[str, float], landmarks: dict[str, Vector]) -> list[bpy.types.Object]:
    palette, traits = profile["palette"], profile["traits"]
    objects: list[bpy.types.Object] = []
    sclera_material = make_material("Generated Warm Sclera", "#ded6c5", 0.28)
    iris_material = make_material("Generated Iris", palette["eyes"], 0.32)
    pupil_material = make_material("Generated Pupil", "#201a15", 0.2)
    brow_material = make_material("Generated Brow Blockout", palette["skin"])
    mouth_material = make_material("Generated Mouth Crease", "#382b27", 0.92)
    for side in ("left", "right"):
        eye = landmarks[f"eye_{side}"]
        eye_center = eye + Vector((0, 0.008 * d["head"], 0))
        objects.append(add_sphere(f"ATLAS_FEATURE_SCLERA_{side.upper()}", eye_center,
                                  0.018 * d["head"], sclera_material, (1.0, 0.82, 0.82)))
        iris_center = eye_center + Vector((0, 0.013 * d["head"], 0))
        objects.append(add_sphere(f"ATLAS_FEATURE_EYE_{side.upper()}", iris_center,
                                  0.0095 * d["head"], iris_material, (1.0, 0.48, 0.86)))
        pupil = iris_center + Vector((0, 0.007 * d["head"], 0))
        objects.append(add_sphere(f"ATLAS_FEATURE_PUPIL_{side.upper()}", pupil,
                                  0.004 * d["head"], pupil_material, (1.0, 0.38, 0.84)))
        brow = landmarks[f"eyebrow_{side}"]
        brow = brow + Vector((0, 0.014 * d["head"], 0))
        objects.append(add_sphere(f"ATLAS_FEATURE_BROW_{side.upper()}", brow, 0.018 * d["head"], brow_material,
                                  (1.45, 0.48, 0.36)))
    objects.append(add_mouth_line(d, mouth_material))

    if traits["horns"]:
        horn_material = make_material("Generated Horns", palette["horns"], 0.5)
        crown = landmarks["crown"]
        for side, sign in (("L", -1), ("R", 1)):
            base = Vector((sign * d["head_rx"] * 0.39, -0.018 * d["head"],
                           d["head_z"] + 0.068 * d["head"]))
            horn_depth = 0.095 * d["head"]
            tilt = Vector((sign * 0.28, -0.62, 0.73)).normalized()
            center = base + tilt * (horn_depth * 0.48)
            rotation = tilt.to_track_quat("Z", "Y").to_euler()
            objects.append(add_cone(f"ATLAS_FEATURE_HORN_{side}", center, 0.025 * d["head"],
                                    horn_depth, horn_material, tuple(rotation), 12))
    if traits["tusks"]:
        tusk_material = make_material("Generated Tusks", palette["tusks"], 0.42)
        for side, sign in (("L", -1), ("R", 1)):
            center = Vector((sign * d["head_rx"] * 0.34, d["head_ry"] * 0.95,
                             d["head_z"] - 0.046 * d["head"]))
            objects.append(add_cone(f"ATLAS_FEATURE_TUSK_{side}", center, 0.014 * d["head"],
                                    0.052 * d["head"], tusk_material, (0, -sign * 0.10, 0), 12))
    if traits["pointed_ears"]:
        ear_material = make_material("Generated Ears", palette["skin"])
        for side, sign in (("L", -1), ("R", 1)):
            base = Vector((sign * d["head_rx"] * 0.82, -0.004 * d["head"],
                           d["head_z"] - 0.016 * d["head"]))
            direction = Vector((sign * 0.86, -0.50, 0.06)).normalized()
            ear_depth = 0.095 * d["head"] * d["ear"]
            center = base + direction * (ear_depth * 0.48)
            rotation = direction.to_track_quat("Z", "Y").to_euler()
            objects.append(add_cone(f"ATLAS_FEATURE_EAR_{side}", center,
                                    0.030 * d["head"] * d["ear"], ear_depth,
                                    ear_material, tuple(rotation), 12))
    return objects


def create_reference_trait_features(profile: dict, d: dict[str, float], landmarks: dict[str, Vector]) -> list[bpy.types.Object]:
    """Add only requested traits that are not guaranteed by a seed human mesh."""
    objects: list[bpy.types.Object] = []
    traits, palette = profile["traits"], profile["palette"]
    head_center = landmarks["head"]
    rx = max(d.get("head_rx", 0.06), 0.035) * d.get("head", 1.0)
    ry = max(d.get("head_ry", 0.06), 0.035) * d.get("head", 1.0)
    rz = max(d.get("head_rz", 0.08), 0.045) * d.get("head", 1.0)
    if traits["horns"]:
        material = make_material("Atlas Seed Horns", palette["horns"], 0.5)
        for side, sign in (("L", -1), ("R", 1)):
            direction = Vector((sign * 0.32, -0.55, 0.77)).normalized()
            base = head_center + Vector((sign * rx * 0.38, -ry * 0.10, rz * 0.70))
            depth = rz * 0.85
            objects.append(add_cone(
                f"ATLAS_FEATURE_HORN_{side}", base + direction * (depth * 0.48),
                rx * 0.20, depth, material, tuple(direction.to_track_quat("Z", "Y").to_euler()), 12,
            ))
    if traits["tusks"]:
        material = make_material("Atlas Seed Tusks", palette["tusks"], 0.42)
        for side, sign in (("L", -1), ("R", 1)):
            direction = Vector((sign * 0.18, 0.18, 1.0)).normalized()
            base = head_center + Vector((sign * rx * 0.28, ry * 0.82, -rz * 0.50))
            depth = rz * 0.40 * d.get("jaw", 1.0)
            objects.append(add_cone(
                f"ATLAS_FEATURE_TUSK_{side}", base + direction * (depth * 0.45),
                rx * 0.12, depth, material, tuple(direction.to_track_quat("Z", "Y").to_euler()), 10,
            ))
    if traits["pointed_ears"]:
        material = make_material("Atlas Seed Pointed Ears", palette["skin"])
        for side, sign in (("L", -1), ("R", 1)):
            direction = Vector((sign * 0.90, -0.35, 0.10)).normalized()
            base = head_center + Vector((sign * rx * 0.82, 0.0, -rz * 0.08))
            depth = rx * 0.80 * d.get("ear", 1.0)
            objects.append(add_cone(
                f"ATLAS_FEATURE_EAR_{side}", base + direction * (depth * 0.48),
                ry * 0.28, depth, material, tuple(direction.to_track_quat("Z", "Y").to_euler()), 12,
            ))
    return objects


def parent_preserving_world(obj: bpy.types.Object, parent: bpy.types.Object) -> None:
    bpy.context.view_layer.update()
    world = obj.matrix_world.copy()
    obj.parent = parent
    obj.matrix_parent_inverse = Matrix.Identity(4)
    obj.matrix_world = world
    bpy.context.view_layer.update()


def create_marker_guides(root: bpy.types.Object, landmarks: dict[str, Vector]) -> list[str]:
    names = []
    collection = root.users_collection[0]
    for label, local_position in landmarks.items():
        marker = bpy.data.objects.new(MARKER_PREFIX + label.upper(), None)
        collection.objects.link(marker)
        marker.empty_display_type = "SPHERE"
        marker.empty_display_size = 0.022
        marker.color = (1.0, 0.43, 0.04, 1.0)
        marker.hide_select = True
        # Markers are authored in root-local model coordinates. Parent first,
        # then set local translation directly; reading matrix_world before a
        # depsgraph update used to collapse every guide to the origin.
        marker.parent = root
        marker.matrix_parent_inverse = Matrix.Identity(4)
        marker.location = local_position
        marker["atlas.marker_role"] = label
        marker["atlas.marker_kind"] = "surface" if label.startswith(("eye_", "eyebrow_", "collarbone_")) or label in {"nose", "crown"} else "joint_center"
        marker["atlas.marker_status"] = "template_position_review_required"
        names.append(marker.name)
    return names


def join_as_single_mesh_object(body: bpy.types.Object, features: list[bpy.types.Object]) -> bpy.types.Object:
    bpy.ops.object.select_all(action="DESELECT")
    for obj in [body, *features]:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()
    body.name = "ATLAS_PROCEDURAL_BODY_V1"
    body.data.name = "ATLAS_PROCEDURAL_BODY_V1_MESH"
    body["atlas.mesh_object_count"] = 1
    body["atlas.body_topology"] = "one_continuous_procedural_body_surface_with_attached_feature_islands"
    return body


def classify_body_faces(body: bpy.types.Object, d: dict[str, float]) -> dict[str, list[int]]:
    regions: dict[str, list[int]] = {
        name: [] for name in ("head", "neck", "torso", "left_arm", "right_arm", "left_hand", "right_hand", "left_leg", "right_leg", "left_foot", "right_foot")
    }
    for polygon in body.data.polygons:
        center = polygon.center
        z, x = center.z, center.x
        absolute_x = abs(x)
        side = "left" if x < 0 else "right"
        if z < d["ankle_z"] + 0.06:
            region = f"{side}_foot"
        elif z < d["pelvis_z"] - 0.08:
            region = f"{side}_leg"
        elif d["wrist_z"] - 0.055 <= z <= d["wrist_z"] + 0.045 and absolute_x >= d["wrist_half"] * 0.72:
            region = f"{side}_hand"
        elif d["shoulder_z"] - 0.055 <= z <= d["shoulder_z"] + 0.08 and absolute_x > d["shoulder_half"] * 0.72:
            region = f"{side}_arm"
        elif z >= d["neck_z"] + 0.035:
            region = "head"
        elif z >= d["shoulder_z"] + 0.01 and absolute_x <= d["shoulder_half"] * 0.72:
            region = "neck"
        elif z < d["pelvis_z"] + 0.02 and absolute_x > d["hip_half"] * 0.35:
            region = f"{side}_leg"
        else:
            region = "torso"
        regions[region].append(polygon.index)
    return regions


def add_region_metadata(body: bpy.types.Object, d: dict[str, float]) -> dict:
    regions = classify_body_faces(body, d)
    mesh = body.data
    face_attribute = mesh.attributes.get("atlas_body_region")
    if face_attribute:
        mesh.attributes.remove(face_attribute)
    face_attribute = mesh.attributes.new("atlas_body_region", type="INT", domain="FACE")
    for group in list(body.vertex_groups):
        if group.name.startswith("ATLAS_REGION_"):
            body.vertex_groups.remove(group)
    labels = sorted(regions)
    for region_id, name in enumerate(labels, start=1):
        vertex_ids = sorted({vertex for polygon_id in regions[name] for vertex in mesh.polygons[polygon_id].vertices})
        group = body.vertex_groups.new(name=f"ATLAS_REGION_{name.upper()}")
        if vertex_ids:
            group.add(vertex_ids, 1.0, "REPLACE")
        for polygon_id in regions[name]:
            face_attribute.data[polygon_id].value = region_id
    body["atlas.body_region_schema"] = "atlas-generated-body-regions/v1"
    return {
        "schema": "atlas-generated-body-regions/v1",
        "mesh_object": body.name,
        "mesh_vertex_count": len(mesh.vertices),
        "mesh_polygon_count": len(mesh.polygons),
        "region_attribute": "atlas_body_region",
        "region_ids": {name: index for index, name in enumerate(labels, start=1)},
        "regions": regions,
        "landmark_policy": "Named point guides define exact placement; face labels provide coarse semantic surface masks.",
    }


def export_static_preview(body: bpy.types.Object, features: list[bpy.types.Object], output: Path) -> None:
    objects = [body, *features]
    saved = {}
    for obj in objects:
        saved[obj.name] = (obj.parent, obj.matrix_parent_inverse.copy(), obj.matrix_world.copy())
        obj.parent = None
        obj.matrix_world = saved[obj.name][2]
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.hide_set(False)
        obj.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.ops.export_scene.gltf(
        filepath=str(output), export_format="GLB", use_selection=True,
        export_skins=False, export_animations=False, export_morph=True,
        export_materials="EXPORT", export_cameras=False, export_lights=False,
        export_yup=True, export_extras=True,
    )
    for obj in objects:
        parent, parent_inverse, world = saved[obj.name]
        obj.parent = parent
        obj.matrix_parent_inverse = parent_inverse
        obj.matrix_world = world
        obj.select_set(False)


def main() -> None:
    args = arguments()
    build_plan = None
    character_recipe = None
    if args.build_plan:
        build_plan, profile = load_geometry_build_plan(args.build_plan)
        source_profile = build_plan["inputs"]["profile"]["snapshot"]
        profile_path = resolve_project_path(build_plan["inputs"]["profile"]["path"])
        character_recipe = build_plan["inputs"]["character_recipe"]["snapshot"]
    else:
        profile_path = args.profile.resolve()
        profile = load_profile(profile_path)
        source_profile = profile
    if build_plan and args.reference_image:
        raise ValueError("reference images must be declared inputs to a build plan before recipe-driven generation")
    output_dir = args.output_root.resolve() / profile["character_id"]
    blend_output = output_dir / "character_base.blend"
    glb_output = output_dir / "character_base_preview.glb"
    regions_output = output_dir / "body_regions.json"
    record_output = output_dir / "character.json"
    profile_copy = output_dir / "design_profile.json"
    recipe_copy = output_dir / "character_recipe.json"
    plan_copy = output_dir / "geometry_build_plan.json"
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if args.reference_model and args.reference_image:
        raise ValueError("Choose either --reference-image or --reference-model, not both.")
    if not 0.0 <= args.image_fit_strength <= 1.0:
        raise ValueError("--image-fit-strength must be between 0 and 1.")
    image_measurements = measure_front_reference(args.reference_image) if args.reference_image else None
    image_fit_report = None
    image_measurements_path = None
    calibration = profile.get("reference_calibration")
    reference_path = args.reference_model
    if calibration and calibration.get("use") == "geometry_seed":
        declared_source = resolve_project_path(calibration["source_path"])
        if reference_path and reference_path.expanduser().resolve() != declared_source:
            raise ValueError("--reference-model must match the geometry seed declared in the profile")
        reference_path = declared_source
    elif reference_path:
        raise ValueError("--reference-model requires a reviewed geometry_seed declaration in the design profile")
    reference_mode = reference_path is not None
    if reference_mode and not build_plan:
        raise ValueError("reference-seeded builds must use a frozen geometry build plan so the source and calibration record are hash-pinned")
    if not reference_mode and not args.allow_blockout:
        print(
            "No production mesh source is configured. The procedural path creates a low-detail blockout, "
            "not a high-quality model. Supply an explicitly reviewed geometry seed or pass --allow-blockout "
            "to create a concept preview. A front image only guides silhouette width; it cannot supply "
            "hidden geometry, surface detail, or production topology.",
            file=sys.stderr,
            flush=True,
        )
        sys.exit(1)
    source_provenance = {}
    if reference_mode:
        if not calibration or calibration.get("use") != "geometry_seed" or calibration.get("geometry_seed_review", {}).get("status") != "approved":
            raise RuntimeError("Reference geometry requires an explicit approved design-fit, topology, and license review in the profile.")
        reference_path = reference_path.expanduser().resolve(strict=True)
        if calibration and sha256(reference_path) != calibration["source_sha256"]:
            raise RuntimeError("Reference model SHA-256 does not match the profile calibration. Recalibrate the source before generation.")
        if calibration:
            provenance_path = (ROOT / calibration["record"]).resolve(strict=True)
            provenance_record = json.loads(provenance_path.read_text(encoding="utf-8"))
            if provenance_record.get("source_sha256") != calibration["source_sha256"]:
                raise RuntimeError("Reference calibration record does not match the profile source hash.")
            if build_plan:
                frozen_reference = build_plan.get("inputs", {}).get("reference_geometry")
                if not frozen_reference or frozen_reference.get("source", {}).get("sha256") != sha256(reference_path):
                    raise RuntimeError("Reference geometry is not the source frozen into the build plan.")
                if frozen_reference.get("calibration_record", {}).get("sha256") != sha256(provenance_path):
                    raise RuntimeError("Reference calibration record is not the version frozen into the build plan.")
            source_provenance = provenance_record.get("provenance", {})
            if source_provenance.get("license") != calibration["license"]:
                raise RuntimeError("Reference license in the profile does not match the calibration record.")
            source_object_name = provenance_record.get("geometry", {}).get("selected_mesh_object")
            if not source_object_name:
                raise RuntimeError("Reference calibration record does not identify a selected source mesh.")
        body, landmarks, dimensions, anatomical_components = import_reference_body(
            reference_path, profile["body"]["height_cm"] / 100, source_object_name, profile,
        )
        if source_provenance:
            body["atlas.source_title"] = source_provenance.get("title", "")
            body["atlas.source_author"] = source_provenance.get("author", "")
            body["atlas.source_url"] = source_provenance.get("source", "")
            body["atlas.source_license"] = source_provenance.get(
                "license", calibration.get("license", "") if calibration else "",
            )
    else:
        dimensions = build_dimensions(profile)
        landmarks = build_landmarks(dimensions)
        body = create_body(profile, dimensions)
        body["atlas.neutral_pose"] = DEFAULT_NEUTRAL_POSE
        anatomical_components = validate_anatomical_connectivity(body)

    try:
        topology_report = validate_shoulder_core(
            [tuple(vertex.co) for vertex in body.data.vertices],
            [tuple(edge.vertices) for edge in body.data.edges],
            [tuple(polygon.vertices) for polygon in body.data.polygons],
            shoulder_height=dimensions["shoulder_z"],
            shoulder_half_width=dimensions["shoulder_half"],
        )
    except TopologyValidationError as error:
        print(str(error), file=sys.stderr, flush=True)
        # Blender can report a successful process status after an uncaught
        # Python exception. Return nonzero so scripts and CI honor this gate.
        sys.exit(1)
    # The silhouette operation changes vertex positions only, never mesh
    # connectivity. Run the structural shoulder gate first so an unusual
    # image width cannot move real arm vertices outside its spatial probes.
    if image_measurements:
        image_fit_report, scale_at_z = fit_mesh_to_front_profile(
            body.data.vertices, image_measurements, args.image_fit_strength,
        )
        body.data.update()
        landmarks = {
            name: Vector((point.x * scale_at_z(point.z), point.y, point.z))
            for name, point in landmarks.items()
        }
    body["atlas.shoulder_core_connected"] = True
    body["atlas.topology_report"] = json.dumps(topology_report, sort_keys=True)
    body["atlas.generation_quality_tier"] = "reference_seed_review" if reference_mode else "blockout_only"

    # A failed topology gate must not leave a partially updated review package.
    output_dir.mkdir(parents=True, exist_ok=True)
    profile_copy.write_text(json.dumps(source_profile, indent=2) + "\n", encoding="utf-8")
    if character_recipe:
        recipe_copy.write_text(json.dumps(character_recipe, indent=2) + "\n", encoding="utf-8")
    if build_plan:
        plan_copy.write_text(json.dumps(build_plan, indent=2) + "\n", encoding="utf-8")
    if image_measurements:
        image_measurements_path = output_dir / "image_measurements.json"
        image_measurements["fit"] = image_fit_report
        image_measurements_path.write_text(json.dumps(image_measurements, indent=2) + "\n", encoding="utf-8")
    if not reference_mode:
        landmarks = project_surface_landmarks(body, landmarks)
        features = create_features(profile, dimensions, landmarks)
        body = join_as_single_mesh_object(body, features)
    else:
        features = create_reference_trait_features(profile, dimensions, landmarks)
        if features:
            body = join_as_single_mesh_object(body, features)
        body["atlas.body_topology"] = "licensed_reference_mesh_with_profile_adaptations_and_trait_islands"
        body["atlas.mesh_object_count"] = 1
    region_document = add_region_metadata(body, dimensions)
    regions_output.write_text(json.dumps(region_document, indent=2) + "\n", encoding="utf-8")
    features = []
    root = bpy.data.objects.new("ATLAS_GENERATED_CHARACTER_ROOT", None)
    bpy.context.scene.collection.objects.link(root)
    root.empty_display_type = "CIRCLE"
    root["atlas.character_id"] = profile["character_id"]
    root["atlas.profile_schema"] = profile["schema"]
    if build_plan:
        root["atlas.geometry_build_plan_sha256"] = build_plan["plan_sha256"]
        root["atlas.character_recipe_sha256"] = build_plan["inputs"]["character_recipe"]["sha256"]
    root["atlas.generator_version"] = GENERATOR_VERSION
    root["atlas.base_review_status"] = "review_required"
    root["atlas.next_stage"] = "geometry_review"
    root["atlas.neutral_pose"] = DEFAULT_NEUTRAL_POSE
    parent_preserving_world(body, root)
    marker_names = create_marker_guides(root, landmarks)

    bpy.context.view_layer.update()
    target_height_m = profile["body"]["height_cm"] / 100
    source_height_m = body.dimensions.z
    if source_height_m <= 1e-5:
        raise RuntimeError("Generated character has an invalid zero-height bounding box")
    root.scale = (target_height_m / source_height_m,) * 3
    scene = bpy.context.scene
    scene["atlas.character_profile"] = json.dumps(profile, sort_keys=True)
    scene["atlas.character_actions"] = ",".join(profile["actions"])
    scene["atlas.character_style"] = profile["style"]
    scene["atlas.character_record_path"] = record_output.name
    bpy.ops.object.select_all(action="DESELECT")
    body.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_output))
    export_static_preview(body, features, glb_output)

    record = {
        "schema": "atlas-generated-character/v1",
        "character_id": profile["character_id"],
        "display_name": profile["display_name"],
        "design_profile_schema": profile["schema"],
        "design_profile": source_profile,
        "effective_build_profile": profile,
        "character_recipe": ({
            "schema": character_recipe["schema"],
            "path": recipe_copy.name,
            "sha256": sha256(recipe_copy),
            "grammar": character_recipe["grammar"],
            "draft_rules_applied": character_recipe.get("draft_rules_applied", False),
        } if character_recipe else None),
        "geometry_build_plan": ({
            "schema": build_plan["schema"],
            "path": plan_copy.name,
            "sha256": sha256(plan_copy),
            "plan_sha256": build_plan["plan_sha256"],
        } if build_plan else None),
        "generator_version": GENERATOR_VERSION,
        "neutral_pose": DEFAULT_NEUTRAL_POSE,
        "pipeline_stage": "base_generated",
        "generation_quality": {
            "tier": "reference_seed_review" if reference_mode else "blockout_only",
            "production_ready": False,
            "reason": (
                "Source geometry and materials are retained for review; this does not establish target-design fit."
                if reference_mode else
                "Deterministic parametric geometry is a concept blockout, not a high-detail sculpt or finished mesh."
            ),
        },
        "base_review_status": "review_required",
        "next_stage": "geometry_review",
        "rigging": {
            "required_for_mesh_review": False,
            "armature_generated": False,
            "skin_weights_generated": False,
            "animation_generated": False,
        },
        "base_template": profile["base_template"],
        "skeleton_id": None,
        "actions_requested": profile["actions"],
        "marker_guides": marker_names,
        "mesh": {
            "object_count": 1,
            "object_name": body.name,
            "vertex_count": len(body.data.vertices),
            "polygon_count": len(body.data.polygons),
            "connected_body_surface": len(anatomical_components) == 1,
            "anatomical_connected_components": len(anatomical_components),
            "shoulder_core_connected": topology_report["shoulder_core_connected"],
            "axilla_stitched_sides": body.get("atlas.axilla_stitched_sides", 0),
            "source_mode": "licensed_reference_mesh_seed" if reference_mode else "procedural_image_fit" if image_measurements else "procedural_parametric",
            "feature_geometry": "source topology islands within one mesh object" if reference_mode else "separate islands inside the same Blender mesh object",
            "topology_validation": topology_report,
        },
        "anatomical_landmarks": {
            name: [round(component * root.scale[0], 6) for component in point]
            for name, point in sorted(landmarks.items())
        },
        "landmark_coordinate_frame": "ATLAS_GENERATED_CHARACTER_ROOT local meters; root scale applied",
        "files": {
            "blend": blend_output.name,
            "preview_glb": glb_output.name,
            "profile": profile_copy.name,
            "body_regions": regions_output.name,
            **({"character_recipe": recipe_copy.name} if character_recipe else {}),
            **({"geometry_build_plan": plan_copy.name} if build_plan else {}),
            **({"image_measurements": image_measurements_path.name} if image_measurements_path else {}),
        },
        "sha256": {
            "design_profile": sha256(profile_copy),
            "blend": sha256(blend_output),
            "preview_glb": sha256(glb_output),
            "body_regions": sha256(regions_output),
            **({"character_recipe": sha256(recipe_copy)} if character_recipe else {}),
            **({"geometry_build_plan": sha256(plan_copy)} if build_plan else {}),
            **({"image_measurements": sha256(image_measurements_path)} if image_measurements_path else {}),
        },
        "source_model": ({
            "path": str(reference_path),
            "sha256": sha256(reference_path),
            "license": calibration["license"] if calibration else "unspecified; verify before redistribution",
            "title": source_provenance.get("title"),
            "author": source_provenance.get("author"),
            "url": source_provenance.get("source"),
            "selected_mesh_object": source_object_name if reference_mode else None,
            "calibration_record": calibration["record"] if calibration else None,
            "calibration_record_sha256": sha256(provenance_path) if reference_mode else None,
            "geometry_seed_review": calibration.get("geometry_seed_review") if calibration else None,
            "source_mesh_baked_without_source_rig": True,
        } if reference_mode else None),
        "image_reference": ({
            "measurements_file": image_measurements_path.name,
            "source_image": image_measurements["source_image"],
            "source_sha256": image_measurements["source_sha256"],
            "method": image_measurements["inference_policy"],
            "fit": image_fit_report,
        } if image_measurements else None),
        "limitations": ([
            "Visible base geometry and materials are baked from the licensed reference; source disconnected islands remain inside one mesh object.",
            "The source rig and animation were removed. Arm and hand components were repositioned rigidly into the Atlas T-pose; inspect wrist seams and intersections.",
            "The source torso and upper-arm boundary arcs are stitched with interpolated mesh rows at the axilla; inspect the blended surface before accepting the base.",
            "Atlas marker guides are fitted from source rest-pose bone locations transformed with the arms and require manual review.",
            "Requested actions are rig requirements; this step does not generate an Atlas skeleton, skin weights, or animations.",
            "The preview is a static model; approval is required before Atlas rig marker placement.",
        ] if reference_mode else ([
            "The front image constrains only horizontal silhouette widths; depth, side anatomy, and the unseen back are inferred from the symmetric Atlas procedural prior.",
            "Foreground extraction uses classical alpha or corner-color thresholding; busy backgrounds, perspective, and non-front poses can produce misleading measurements.",
            "The fit changes body width by height only. It does not infer surface detail, materials, texture, rigging, or animation from the image.",
            "The base is generated from parametric metaball anatomy; creature-specific anatomy remains approximate.",
            "Body and feature shells are one mesh object; feature shells remain separate geometric islands and need visual review.",
            "Requested actions are rig requirements; this step does not generate skeletons, skin weights, or animations.",
            "The preview is an unrigged static model; approval is required before rig marker placement.",
        ] if image_measurements else [
            "The base is generated from parametric metaball anatomy; creature-specific anatomy remains approximate.",
            "Body and feature shells are one mesh object; feature shells remain separate geometric islands and need visual review.",
            "Requested actions are rig requirements; this step does not generate skeletons, skin weights, or animations.",
            "The preview is an unrigged static model; approval is required before rig marker placement.",
        ])),
    }
    record_output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    source_label = "reference-seeded" if reference_mode else "image-fitted procedural" if image_measurements else "parametric"
    print(f"Generated {source_label} character base: {blend_output}")
    print(f"Static review preview: {glb_output}")
    print(f"Review record: {record_output}")
    print(f"Body markers: {len(marker_names)}; intended actions: {', '.join(profile['actions'])}")
    if image_measurements:
        print(
            f"Image fit: {image_measurements['source_image']}; symmetric front silhouette fitted, "
            "hidden depth inferred from Atlas anatomy rules"
        )
    if reference_mode:
        print(f"Seed mesh: {reference_path.name}; baked visible source mesh, removed source rig/animation")
    print(f"Neutral authoring pose: {DEFAULT_NEUTRAL_POSE}")
    print("Base status: review_required; Atlas rig and weights are not generated at this stage")


if __name__ == "__main__":
    main()
