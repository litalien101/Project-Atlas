import unittest

from tools.characters.character_topology import (
    TopologyValidationError,
    analyze_mesh_topology,
    validate_shoulder_core,
)


class CharacterTopologyTests(unittest.TestCase):
    def setUp(self):
        # A compact torso with bilateral arms. Coordinates use the same
        # normalized frame as the Blender generator.
        self.vertices = [(-0.08, 0.0, 0.70), (0.0, 0.0, 0.70), (0.08, 0.0, 0.70)]
        self.vertices += [(-0.30 - index * 0.018, 0.0, 0.70) for index in range(8)]
        self.vertices += [(0.30 + index * 0.018, 0.0, 0.70) for index in range(8)]
        self.vertices += [(0.0, 0.0, 0.96), (0.01, 0.0, 0.96)]
        self.connected_edges = [(0, 1), (1, 2), (1, 3), (9, 10)]
        self.connected_edges += [(index, index + 1) for index in range(3, 10)]
        self.connected_edges += [(1, 11), (11, 12)]
        self.connected_edges += [(index, index + 1) for index in range(12, 18)]
        # An intentional feature island outside the shoulder probe.
        self.connected_edges += [(19, 20)]

    def test_connected_torso_and_bilateral_arms_allow_feature_islands(self):
        report = validate_shoulder_core(
            self.vertices, self.connected_edges, [],
            shoulder_height=0.70, shoulder_half_width=0.16,
        )

        self.assertTrue(report["shoulder_core_connected"])
        self.assertEqual(report["connected_components"], 2)
        self.assertEqual(report["shoulder_core_components"]["torso"],
                         report["shoulder_core_components"]["left"])
        self.assertEqual(report["shoulder_core_components"]["torso"],
                         report["shoulder_core_components"]["right"])

    def test_detached_shoulder_components_fail_the_gate(self):
        detached_edges = [(0, 1), (1, 2), (3, 10), (11, 18), (19, 20)]

        with self.assertRaises(TopologyValidationError) as caught:
            validate_shoulder_core(
                self.vertices, detached_edges, [],
                shoulder_height=0.70, shoulder_half_width=0.16,
            )

        report = caught.exception.report
        self.assertFalse(report["shoulder_core_connected"])
        self.assertNotEqual(report["shoulder_core_components"]["torso"],
                            report["shoulder_core_components"]["left"])

    def test_topology_report_counts_open_and_non_manifold_edges(self):
        vertices = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1)]
        edges = [(0, 1), (1, 2), (2, 0), (0, 3), (3, 1), (0, 4), (4, 1)]
        faces = [(0, 1, 2), (1, 0, 3), (0, 1, 4)]

        report, _ = analyze_mesh_topology(vertices, edges, faces)

        self.assertEqual(report["connected_components"], 1)
        self.assertEqual(report["boundary_edge_count"], 6)
        self.assertEqual(report["non_manifold_edge_count"], 1)


if __name__ == "__main__":
    unittest.main()
