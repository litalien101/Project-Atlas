"""Explainable decisions assembled from persisted simulation and policy records."""

from __future__ import annotations

from typing import Any


def generate_decision(simulation: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    if not simulation.get("simulation_id") or policy.get("simulation_id") != simulation["simulation_id"]:
        raise ValueError("The policy evaluation must reference the supplied simulation.")
    if policy.get("status") not in {"blocked", "eligible_for_human_review"}:
        raise ValueError("The policy evaluation has an unsupported status.")
    allowed = policy["status"] == "eligible_for_human_review"
    confidence = simulation.get("confidence", {})
    if not isinstance(confidence, dict) or not isinstance(confidence.get("value"), (int, float)):
        raise ValueError("A decision requires a confidence-bearing simulation.")
    if allowed:
        rationale = "Simulation and policy checks permit human review. Approval is still required before any world change."
        outcome = "approve"
        status = "awaiting_human_approval"
    else:
        details = "; ".join(item["reason"] for item in policy.get("violations", []))
        rationale = f"Policy blocks this proposal. {details}".strip()
        outcome = "reject"
        status = "blocked_by_policy"
    return {
        "simulation_id": simulation["simulation_id"],
        "policy_evaluation_id": policy["evaluation_id"],
        "recommended_output": outcome,
        "status": status,
        "rationale": rationale,
        "policy_status": policy["status"],
        "policy_violations": policy.get("violations", []),
        "policy_version": policy.get("policy_version"),
        "policy_digest_sha256": policy.get("policy_digest_sha256"),
        "proposed_change": simulation["proposed_change"],
        "affected_systems": simulation.get("affected_systems", []),
        "affected_entities": simulation.get("affected_entities", []),
        "projected_risk": simulation.get("projected_risk"),
        "confidence": confidence,
        "evidence_references": simulation.get("evidence_references", []),
        "human_approval_required": True,
        "world_change_applied": False,
    }
