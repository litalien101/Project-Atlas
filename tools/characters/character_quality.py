"""Fail-closed checks for advancing a character base to rig authoring."""

from __future__ import annotations

from typing import Any


def is_rigging_candidate(record: dict[str, Any]) -> bool:
    """Return true only for an accepted, reviewed, still-nonproduction sculpt."""
    quality = record.get("generation_quality")
    review = record.get("base_review")
    hashes = record.get("sha256")
    mesh = record.get("mesh")
    if not isinstance(mesh, dict):
        return False
    return bool(
        record.get("base_review_status") == "accepted"
        and isinstance(quality, dict)
        and quality.get("tier") == "blockout_only"
        and quality.get("production_ready") is False
        and isinstance(review, dict)
        and review.get("decision") == "accept"
        and review.get("approval_scope") == "rigging_candidate_only"
        and review.get("reviewed_sculpt") is True
        and review.get("reviewed_t_pose") is True
        and record.get("neutral_pose") == "t_pose_fingers_spread"
        and isinstance(hashes, dict)
        and isinstance(hashes.get("preview_glb"), str)
        and review.get("preview_sha256") == hashes.get("preview_glb")
        and mesh.get("shoulder_core_connected") is True
    )
