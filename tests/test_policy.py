import unittest
from pathlib import Path

from atlas_server.policy import PolicyEngine
from atlas_server.decision import generate_decision


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "specs" / "atlas" / "specs" / "atlas-policy-engine.yaml"


def simulation(change, *, activations=1, confidence=1.0, risk="low"):
    return {
        "simulation_id": "4c2bb16c-340d-4d18-bc1d-c6a40da014c8",
        "simulation_as_of_sequence": 9,
        "proposed_change": change,
        "baseline_rules": {"beacon.lumen_reed_cost": 3},
        "baseline": {"recorded_activation_events": activations},
        "confidence": {"value": confidence},
        "projected_risk": risk,
    }


class PolicyEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = PolicyEngine(POLICY_PATH)

    def test_change_within_creator_policy_is_eligible_only_for_human_review(self):
        result = self.engine.evaluate(simulation({"rule": "beacon.lumen_reed_cost", "value": 3}))
        self.assertEqual(result["status"], "eligible_for_human_review")
        self.assertTrue(result["human_approval_required"])
        self.assertFalse(result["autonomous_world_changes_enabled"])
        self.assertFalse(result["world_change_applied"])

    def test_change_beyond_creator_limit_is_blocked(self):
        result = self.engine.evaluate(simulation({"rule": "beacon.lumen_reed_cost", "value": 2}))
        self.assertEqual(result["status"], "blocked")
        self.assertIn("resource_requirements.max_cost_change_percent",
                      {violation["policy"] for violation in result["violations"]})

    def test_unscoped_or_under_evidenced_changes_fail_closed(self):
        result = self.engine.evaluate(simulation({"rule": "combat.damage", "value": 12}, activations=0,
                                                 confidence=.84, risk="high"))
        policies = {violation["policy"] for violation in result["violations"]}
        self.assertEqual(result["status"], "blocked")
        self.assertTrue({"explicit_policy_required", "minimum_observed_outcomes",
                         "confidence_threshold", "projected_risk"}.issubset(policies))

    def test_decision_requires_human_approval_and_carries_simulation_evidence(self):
        persisted = simulation({"rule": "beacon.lumen_reed_cost", "value": 3})
        policy = {"simulation_id": persisted["simulation_id"], "evaluation_id": "policy-id",
                  "status": "eligible_for_human_review", "violations": []}
        result = generate_decision(persisted, policy)
        self.assertEqual(result["recommended_output"], "approve")
        self.assertEqual(result["status"], "awaiting_human_approval")
        self.assertTrue(result["human_approval_required"])
        self.assertFalse(result["world_change_applied"])

    def test_decision_cannot_mix_simulation_and_policy_evaluation(self):
        persisted = simulation({"rule": "beacon.lumen_reed_cost", "value": 3})
        policy = {"simulation_id": "other-simulation", "evaluation_id": "policy-id",
                  "status": "eligible_for_human_review", "violations": []}
        with self.assertRaisesRegex(ValueError, "reference the supplied simulation"):
            generate_decision(persisted, policy)


if __name__ == "__main__":
    unittest.main()
