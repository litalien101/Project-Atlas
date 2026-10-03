"""Explainable technical triage for humanoid source-inspection dossiers.

This module reports measurable intake concerns. It does not rate visual quality,
semantic fit, rights, source independence, or learning eligibility.
"""
from __future__ import annotations

import math
from typing import Any

SCHEMA = "atlas-character-source-screening/v1"
TOOL_VERSION = "1.0.0"
PROFILE_ID = "humanoid-anatomy-reference-v1"


def _check(
    check_id: str,
    reason_code: str,
    status: str,
    severity: str,
    summary: str,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "reason_code": reason_code,
        "status": status,
        "severity": severity,
        "summary": summary,
        "evidence": evidence or {},
    }


def screen_inspection(dossier: dict[str, Any]) -> dict[str, Any]:
    """Return deterministic triage from a source-inspection dossier.

    Topology flags are review prompts, not automatic rejection thresholds.
    Geometry complexity is intentionally not scored as quality.
    """
    source = dossier.get("source", {})
    meshes = dossier.get("mesh_objects", [])
    focus_name = dossier.get("focus_object")
    focus = next((mesh for mesh in meshes if mesh.get("name") == focus_name), None)
    checks: list[dict[str, Any]] = []
    hard_concern = False
    needs_review = False

    if not meshes:
        checks.append(_check("mesh_geometry", "MESH_OBJECTS_MISSING", "concern", "blocking",
                             "The dossier contains no mesh objects."))
        hard_concern = True
    elif focus is None:
        checks.append(_check(
            "focus_mesh", "FOCUS_MESH_NOT_SELECTED", "unknown", "warning",
            "No unambiguous focus mesh is identified; select the source mesh to evaluate.",
            {"mesh_object_count": len(meshes)},
        ))
        needs_review = True
    else:
        checks.append(_check(
            "focus_mesh", "FOCUS_MESH_FOUND", "clear", "info",
            "A focus mesh is identified in the dossier.", {"focus_object": focus_name},
        ))
        counts = {
            "vertices": focus.get("vertex_count"),
            "polygons": focus.get("polygon_count"),
        }
        if any(not isinstance(value, int) or value <= 0 for value in counts.values()):
            checks.append(_check(
                "usable_geometry", "FOCUS_GEOMETRY_EMPTY", "concern", "blocking",
                "The focus mesh has no usable vertex or polygon geometry.", counts,
            ))
            hard_concern = True
        else:
            checks.append(_check(
                "usable_geometry", "FOCUS_GEOMETRY_PRESENT", "clear", "info",
                "The focus mesh has vertices and polygons.", counts,
            ))

        box = focus.get("world_bounds") or {}
        dims = box.get("dimensions")
        if not isinstance(dims, list) or len(dims) != 3:
            checks.append(_check("world_bounds", "WORLD_BOUNDS_MISSING", "unknown", "warning",
                                 "World-space bounds are missing or incomplete."))
            needs_review = True
        elif (any(not isinstance(value, (int, float)) or not math.isfinite(value) for value in dims)
              or any(value <= 1e-9 for value in dims)):
            checks.append(_check(
                "world_bounds", "WORLD_BOUNDS_INVALID", "concern", "blocking",
                "At least one focus-mesh world-space dimension is zero or invalid.",
                {"dimensions": dims},
            ))
            hard_concern = True
        else:
            checks.append(_check("world_bounds", "WORLD_BOUNDS_VALID", "clear", "info",
                                 "All three world-space dimensions are positive.", {"dimensions": dims}))

        topology = focus.get("topology") or {}
        topology_findings: dict[str, Any] = {}
        for key in ("boundary_edge_count", "non_manifold_edge_count", "wire_edge_count"):
            value = topology.get(key)
            if not isinstance(value, int):
                topology_findings[key] = None
            elif value > 0:
                topology_findings[key] = value
        zero_area = (focus.get("normals") or {}).get("zero_area_polygon_count")
        if not isinstance(zero_area, int):
            topology_findings["zero_area_polygon_count"] = None
        elif zero_area > 0:
            topology_findings["zero_area_polygon_count"] = zero_area
        components = topology.get("connected_component_count")
        if not isinstance(components, int):
            topology_findings["connected_component_count"] = None
        elif components < 1 or components > 1:
            topology_findings["connected_component_count"] = components
        if topology_findings:
            checks.append(_check(
                "topology_review", "TOPOLOGY_FLAGS_PRESENT", "flag", "warning",
                "Topology metrics contain possible defects or disconnected parts; review in context. These counts do not automatically reject the model.",
                topology_findings,
            ))
            needs_review = True
        else:
            checks.append(_check(
                "topology_review", "TOPOLOGY_NO_FLAGS", "clear", "info",
                "No boundary, non-manifold, wire, zero-area, or multiple-component flags were reported.",
            ))

        if focus.get("evaluated_geometry_reliable") is False:
            driver_count = len(focus.get("driver_curves", []))
            checks.append(_check(
                "evaluated_geometry", "EVALUATED_GEOMETRY_UNRELIABLE", "flag", "warning",
                "Evaluated geometry may not reflect intended controls; raw source mesh metrics remain separately reported.",
                {"driver_curve_count": driver_count},
            ))
            needs_review = True
        elif focus.get("evaluated_geometry_reliable") is True:
            checks.append(_check("evaluated_geometry", "EVALUATED_GEOMETRY_RELIABLE", "clear", "info",
                                 "The dossier reports evaluated geometry as reliable."))
        else:
            checks.append(_check("evaluated_geometry", "EVALUATED_GEOMETRY_RELIABILITY_UNKNOWN", "unknown", "warning",
                                 "Evaluated-geometry reliability is not recorded."))
            needs_review = True

    if hard_concern:
        outcome = "technical_concern"
        rationale = "The dossier reports a blocking geometry or bounds concern; inspect the source before using it."
    elif needs_review:
        outcome = "needs_human_review"
        rationale = "Technical intake is incomplete or reports conditions requiring contextual review."
    else:
        outcome = "technically_promising"
        rationale = "The measured technical checks found no blocking concerns; this only makes the source promising for human review."

    return {
        "schema": SCHEMA,
        "tool": {"name": "character_source_screening.py", "version": TOOL_VERSION},
        "screening_profile": {
            "profile_id": PROFILE_ID,
            "archetype_id": "humanoid",
            "intended_use": "general_humanoid_anatomy_reference",
        },
        "source": {"path": source.get("path"), "sha256": source.get("sha256")},
        "triage": {"outcome": outcome, "rationale": [rationale]},
        "technical_checks": checks,
        "human_review": {
            "required": True,
            "unresolved_gates": [
                "Confirm intended archetype and the specific anatomy/measurement question this source can support.",
                "Visually review pose, orientation, completeness, visibility, and source quality from useful views.",
                "Review topology flags in context, including whether disconnected parts are intentional.",
                "Confirm source identity and lineage so variants or derivatives are not counted as independent examples.",
                "Review license evidence and permitted use for the intended analysis or training purpose.",
            ],
        },
        "eligibility": {
            "learning": "not_approved",
            "rights": "review_required",
            "runtime": "not_approved",
        },
        "limitations": [
            "This profile screens technical facts from a humanoid dossier only; it does not assess visual quality or infer anatomy.",
            "It does not detect clothing, occlusion, pose suitability, archetype compatibility, duplicate lineage, or license validity.",
            "No polygon-count threshold is used as a quality score.",
            "A technically_promising outcome is not learning, geometry-seed, or runtime approval.",
        ],
    }
