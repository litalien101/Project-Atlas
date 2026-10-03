import unittest

from atlas_server.analytics import summarize_events


class WorldAnalyticsTests(unittest.TestCase):
    def test_analytics_are_deterministic_and_only_report_observed_events(self):
        actor_a = "player-a"
        actor_b = "player-b"
        events = [
            {"sequence": 1, "type": "ResourceGathered", "at": "2026-10-02T10:00:00Z",
             "actor_id": actor_a, "detail": {"quantity": 1}},
            {"sequence": 2, "type": "NPCSpokenTo", "at": "2026-10-02T10:05:00Z",
             "actor_id": actor_a, "detail": {"first_meeting": True}},
            {"sequence": 3, "type": "CreatureDamaged", "at": "2026-10-03T10:00:00Z",
             "actor_id": actor_b, "detail": {"damage": 1, "player_damage": 7, "defeated": True}},
            {"sequence": 4, "type": "BeaconAwakened", "at": "2026-10-03T10:15:00Z",
             "actor_id": actor_b, "detail": {"offering": {"lumen_reed": 3}}},
        ]

        result = summarize_events(events, after_sequence=0)
        self.assertEqual(result["window"], {"after_sequence": 0, "through_sequence": 4,
                                           "event_count": 4, "has_more": False})
        self.assertEqual(result["activity"]["active_actor_count"], 2)
        self.assertEqual(result["social"], {"npc_conversations": 1, "first_meetings": 1})
        self.assertEqual(result["progression"]["beacons_awakened"], 1)
        self.assertEqual(result["resources"], {"lumen_reeds_gathered": 1,
                                               "lumen_reeds_offered": 3,
                                               "lumen_reed_net_flow": -2})
        self.assertEqual(result["combat"], {"attacks_resolved": 1, "damage_dealt": 1,
                                            "damage_received": 7, "creatures_defeated": 1,
                                            "guards_raised": 0, "dodges_performed": 0})
        self.assertEqual([day["date"] for day in result["timeline"]], ["2026-10-02", "2026-10-03"])
        self.assertTrue(any("Retention" in item for item in result["limitations"]))


if __name__ == "__main__":
    unittest.main()
