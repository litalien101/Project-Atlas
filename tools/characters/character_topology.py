"""Mesh-topology diagnostics and pre-export character shoulder gate.

The analyzer uses only Python data structures so the quality gate can be
tested without starting Blender. Coordinates are expected in the generator's
normalized, root-local frame (approximately one unit tall).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Sequence


@dataclass
class TopologyValidationError(ValueError):
    """A generated character failed a structural topology requirement."""

    report: dict

    def __str__(self) -> str:
        sides = self.report.get("shoulder_core_components", {})
        return (
            "Character shoulder topology failed: the torso and both substantial "
            "upper-arm regions must share one connected component (at least 8 "
            f"probe vertices per side; component ids: {sides}). "
            f"Diagnostics: {self.report}"
        )


def analyze_mesh_topology(
    vertices: Sequence[Sequence[float]],
    edges: Iterable[Sequence[int]],
    faces: Iterable[Sequence[int]],
) -> tuple[dict, list[int]]:
    """Return component, boundary-edge, and non-manifold diagnostics.

    Edges with no incident faces are ignored for boundary classification. A
    boundary edge belongs to one face; a non-manifold edge belongs to more
    than two. Components are connected through mesh edges, as expected for
    Blender mesh topology.
    """
    adjacency = [set() for _ in vertices]
    for edge in edges:
        if len(edge) != 2:
            continue
        a, b = int(edge[0]), int(edge[1])
        if a < 0 or b < 0 or a >= len(vertices) or b >= len(vertices):
            raise ValueError(f"Mesh edge references an invalid vertex: {edge}")
        adjacency[a].add(b)
        adjacency[b].add(a)

    labels = [-1] * len(vertices)
    sizes: list[int] = []
    members: list[list[int]] = []
    for start in range(len(vertices)):
        if labels[start] >= 0:
            continue
        component_id = len(sizes)
        labels[start] = component_id
        stack = [start]
        size = 0
        component_vertices = []
        while stack:
            current = stack.pop()
            size += 1
            component_vertices.append(current)
            for neighbor in adjacency[current]:
                if labels[neighbor] < 0:
                    labels[neighbor] = component_id
                    stack.append(neighbor)
        sizes.append(size)
        members.append(component_vertices)

    face_edge_uses: Counter[tuple[int, int]] = Counter()
    for face in faces:
        if len(face) < 3:
            continue
        indices = [int(index) for index in face]
        if any(index < 0 or index >= len(vertices) for index in indices):
            raise ValueError("Mesh face references an invalid vertex")
        for offset, a in enumerate(indices):
            b = indices[(offset + 1) % len(indices)]
            face_edge_uses[tuple(sorted((a, b)))] += 1

    diagnostics = {
        "connected_components": len(sizes),
        "component_sizes": sorted(sizes, reverse=True),
        "component_summaries": [
            {
                "id": component_id,
                "vertices": len(indices),
                "center": [round(sum(float(vertices[index][axis]) for index in indices) / len(indices), 3)
                           for axis in range(3)],
                "bounds": [
                    [round(min(float(vertices[index][axis]) for index in indices), 3),
                     round(max(float(vertices[index][axis]) for index in indices), 3)]
                    for axis in range(3)
                ],
            }
            for component_id, indices in enumerate(members)
        ],
        "boundary_edge_count": sum(uses == 1 for uses in face_edge_uses.values()),
        "non_manifold_edge_count": sum(uses > 2 for uses in face_edge_uses.values()),
    }
    return diagnostics, labels


def validate_shoulder_core(
    vertices: Sequence[Sequence[float]],
    edges: Iterable[Sequence[int]],
    faces: Iterable[Sequence[int]],
    *,
    shoulder_height: float,
    shoulder_half_width: float,
) -> dict:
    """Require the torso anchor and both upper-arm sockets to be connected.

    This deliberately does not require every vertex in a character mesh to
    belong to one component. Eyes, teeth, accessories, and some licensed seed meshes
    may contain intentional islands. It identifies the central chest region
    and the substantial outer shoulder regions, then checks that each resolves
    to the same edge-connected component.
    """
    mesh_report, component_ids = analyze_mesh_topology(vertices, edges, faces)
    torso_half_width = max(0.10, min(0.20, shoulder_half_width))
    outer_arm_threshold = max(0.28, shoulder_half_width * 1.75)
    outer_arm_limit = max(outer_arm_threshold + 0.16, shoulder_half_width * 2.75)
    torso_probe_ids = [
        component_ids[index]
        for index, point in enumerate(vertices)
        if abs(float(point[0])) <= torso_half_width
        and shoulder_height - 0.22 <= float(point[2]) <= shoulder_height - 0.04
    ]
    torso_center_limit = max(0.15, min(0.25, shoulder_half_width * 1.5))
    torso_candidates = [
        summary for summary in mesh_report["component_summaries"]
        if abs(summary["center"][0]) <= torso_center_limit
        and shoulder_height - 0.22 <= summary["center"][2] <= shoulder_height + 0.05
    ]
    if len(mesh_report["component_summaries"]) == 1:
        torso_component = 0
    elif torso_candidates:
        torso_component = max(torso_candidates, key=lambda item: item["vertices"])["id"]
    else:
        torso_counts = Counter(torso_probe_ids)
        torso_component = torso_counts.most_common(1)[0][0] if torso_counts else None

    arm_component_ids: dict[str, int | None] = {}
    arm_region_vertex_counts: dict[str, int] = {}
    for side, sign in (("left", -1), ("right", 1)):
        counts = Counter(
            component_ids[index]
            for index, point in enumerate(vertices)
            if outer_arm_threshold <= float(point[0]) * sign <= outer_arm_limit
            and abs(float(point[2]) - shoulder_height) <= 0.14
        )
        candidate = counts.most_common(1)[0] if counts else (None, 0)
        arm_component_ids[side] = candidate[0]
        arm_region_vertex_counts[side] = candidate[1]

    core_connected = (
        torso_component is not None
        and all(component_id is not None and component_id == torso_component
                for component_id in arm_component_ids.values())
        and all(count >= 8 for count in arm_region_vertex_counts.values())
    )
    report = {
        **mesh_report,
        "shoulder_core_connected": core_connected,
        "shoulder_core_components": {
            "torso": torso_component,
            **arm_component_ids,
        },
        "shoulder_region_vertex_counts": arm_region_vertex_counts,
        "shoulder_probe": {
            "height": round(float(shoulder_height), 6),
            "torso_half_width": round(torso_half_width, 6),
            "torso_center_limit": round(torso_center_limit, 6),
            "outer_arm_threshold": round(outer_arm_threshold, 6),
            "outer_arm_limit": round(outer_arm_limit, 6),
        },
    }
    if not core_connected:
        raise TopologyValidationError(report)
    return report
