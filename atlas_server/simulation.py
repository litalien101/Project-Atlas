"""Evidence-scoped, deterministic what-if simulations for the reference world."""

from __future__ import annotations

from typing import Any

from .world import BEACON_LUMEN_REED_COST


MODEL = "resource_progression"
MODEL_VERSION = "1.0.0"


def run_simulation(events: list[dict[str, Any]], proposed_change: dict[str, Any]) -> dict[str, Any]:
    """Replay recorded resource and beacon events under baseline and candidate rules.

    This is an exact counterfactual over recorded choices, not a forecast of
    player behavior. It deliberately does not synthesize missing player actions.
    """
    if not isinstance(proposed_change, dict) or set(proposed_change) != {"rule", "value"}:
        raise ValueError("A simulation change must contain exactly 'rule' and 'value'.")
    if proposed_change["rule"] != "beacon.lumen_reed_cost":
        raise ValueError("This simulation model supports only beacon.lumen_reed_cost.")
    candidate_cost = proposed_change["value"]
    if isinstance(candidate_cost, bool) or not isinstance(candidate_cost, int) or not 1 <= candidate_cost <= 4:
        raise ValueError("Beacon reed cost must be a whole number between 1 and 4.")

    def replay(cost: int) -> dict[str, Any]:
        inventory: dict[str, int] = {}
        patches: set[str] = set()
        activations: list[str] = []
        blocked: list[str] = []
        gathers = 0
        for event in events:
            detail = event["detail"]
            actor = event["actor_id"]
            if event["type"] == "ResourceGathered" and detail.get("resource") == "lumen_reed":
                patch = detail.get("patch_id")
                quantity = detail.get("quantity")
                if patch not in patches and isinstance(quantity, int) and quantity > 0:
                    patches.add(patch)
                    inventory[actor] = inventory.get(actor, 0) + quantity
                    gathers += quantity
            elif event["type"] == "BeaconAwakened":
                if inventory.get(actor, 0) >= cost:
                    inventory[actor] -= cost
                    activations.append(event["event_id"])
                else:
                    blocked.append(event["event_id"])
        return {"reed_gathered": gathers, "recorded_activation_events": len(activations),
                "activation_event_ids": activations, "activation_events_blocked": len(blocked),
                "blocked_event_ids": blocked,
                "remaining_reeds_by_actor": dict(sorted(inventory.items()))}

    baseline = replay(BEACON_LUMEN_REED_COST)
    projected = replay(candidate_cost)
    evidence = [event["event_id"] for event in events
                if event["type"] in {"ResourceGathered", "BeaconAwakened"}]
    return {
        "model": MODEL,
        "model_version": MODEL_VERSION,
        "simulation_kind": "deterministic_recorded_event_counterfactual",
        "affected_systems": ["progression", "resource_economy"],
        "baseline_rules": {"beacon.lumen_reed_cost": BEACON_LUMEN_REED_COST},
        "proposed_change": proposed_change,
        "baseline": baseline,
        "projected": projected,
        "expected_result": {
            "recorded_activation_delta": projected["recorded_activation_events"] - baseline["recorded_activation_events"],
            "recorded_events_replayed": len(evidence),
            "evidence_event_ids": evidence,
        },
        "confidence": {"value": 1.0, "scope": "exact for these recorded events under the stated rule change",
                       "future_player_behavior": "not modeled"},
        "evidence_references": evidence,
        "projected_risk": ("medium" if not baseline["recorded_activation_events"] else
                           "high" if projected["activation_events_blocked"] else "low"),
        "affected_entities": ["b71e10e4-cb79-5c1e-9355-542c1d82512d",
                              "b40a2c87-93f0-5988-a1fa-2781a3257b0d",
                              "d1de73d7-91b2-5c1e-a6c2-1e7879277533",
                              "e8b0b59e-df17-592b-9faf-91d0d14c84d4",
                              "f84b7c8d-f829-594e-a086-34cde48d7a84"],
        "limitations": [
            "Only recorded lumen-reed gathering and successful beacon-activation attempts are replayed.",
            "The event log does not record failed activation attempts or why players did not try.",
            "This result does not predict future behavior, retention, satisfaction, or population effects.",
            "Simulation output is advisory and does not mutate the production world.",
        ],
    }
