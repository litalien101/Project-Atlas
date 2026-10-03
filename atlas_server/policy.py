"""Fail-closed policy checks for simulated reference-world changes."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from hashlib import sha256

import yaml


class PolicyEngine:
    def __init__(self, policy_path: Path):
        try:
            with policy_path.open("r", encoding="utf-8") as stream:
                policy = yaml.safe_load(stream)
        except (OSError, yaml.YAMLError) as exc:
            raise ValueError(f"Atlas policy contract could not be loaded: {policy_path}") from exc
        if not isinstance(policy, dict) or not isinstance(policy.get("policies"), dict):
            raise ValueError("Atlas policy contract must define a policies mapping.")
        requirements = policy.get("requirements")
        if not isinstance(requirements, dict):
            raise ValueError("Atlas policy contract must define requirements.")
        threshold = requirements.get("confidence_threshold")
        if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not 0 <= threshold <= 1:
            raise ValueError("Atlas recommendation confidence threshold must be between 0 and 1.")
        self.policies = policy["policies"]
        self.requirements = requirements
        if requirements.get("human_approval_required") is not True:
            raise ValueError("Atlas policies cannot disable mandatory human approval.")
        if requirements.get("autonomous_world_changes_enabled") is not False:
            raise ValueError("Autonomous world changes must remain disabled.")
        self.version = policy.get("version")
        self.digest = sha256(policy_path.read_bytes()).hexdigest()

    def evaluate(self, simulation: dict[str, Any]) -> dict[str, Any]:
        """Check one immutable simulation against explicit creator policy."""
        violations: list[dict[str, str]] = []
        proposal = simulation.get("proposed_change")
        if not isinstance(proposal, dict) or simulation.get("simulation_id") is None:
            violations.append({"policy": "simulation_required", "reason": "A persisted simulation is required."})
            proposal = {}
        confidence = simulation.get("confidence", {}).get("value") if isinstance(simulation.get("confidence"), dict) else None
        threshold = float(self.requirements["confidence_threshold"])
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or confidence < threshold:
            violations.append({"policy": "confidence_threshold",
                               "reason": f"Simulation confidence must be at least {threshold:.2f}."})
        if self.requirements.get("simulation_required") is not True:
            violations.append({"policy": "simulation_required", "reason": "Simulation is not enabled by policy."})

        if proposal.get("rule") == "beacon.lumen_reed_cost":
            baseline = simulation.get("baseline_rules", {}).get("beacon.lumen_reed_cost")
            candidate = proposal.get("value")
            cap = self.policies.get("resource_requirements", {}).get("max_cost_change_percent")
            if (isinstance(baseline, bool) or not isinstance(baseline, (int, float)) or baseline <= 0 or
                    isinstance(candidate, bool) or not isinstance(candidate, (int, float)) or
                    isinstance(cap, bool) or not isinstance(cap, (int, float)) or cap < 0):
                violations.append({"policy": "resource_requirements.max_cost_change_percent",
                                   "reason": "The resource-cost proposal or its governing policy is invalid."})
            else:
                change_percent = abs(candidate - baseline) / baseline * 100
                if change_percent > cap:
                    violations.append({"policy": "resource_requirements.max_cost_change_percent",
                                       "reason": f"The {change_percent:g}% change exceeds the creator limit of {cap:g}%."})
        else:
            violations.append({"policy": "explicit_policy_required",
                               "reason": "No creator policy is defined for this proposed rule."})

        if simulation.get("projected_risk") in {"high", "critical"}:
            violations.append({"policy": "projected_risk", "reason": "High or critical projected risk requires modification or delay."})
        if simulation.get("projected_risk") not in {"low", "medium", "high", "critical"}:
            violations.append({"policy": "projected_risk", "reason": "The simulation has no recognized projected-risk level."})
        baseline_activations = simulation.get("baseline", {}).get("recorded_activation_events")
        if not isinstance(baseline_activations, int) or baseline_activations < 1:
            violations.append({"policy": "minimum_observed_outcomes",
                               "reason": "At least one recorded baseline outcome is required for policy review."})

        eligible = not violations
        return {
            "policy_version": self.version,
            "policy_digest_sha256": self.digest,
            "status": "eligible_for_human_review" if eligible else "blocked",
            "eligible_for_human_review": eligible,
            "violations": violations,
            "confidence_threshold": threshold,
            "simulation_id": simulation.get("simulation_id"),
            "simulation_as_of_sequence": simulation.get("as_of_sequence"),
            "human_approval_required": self.requirements.get("human_approval_required") is True,
            "autonomous_world_changes_enabled": self.requirements.get("autonomous_world_changes_enabled") is True,
            "world_change_applied": False,
            "limitations": ["Policy eligibility is not creator approval.",
                            "This evaluation does not change live world rules or state."],
        }
