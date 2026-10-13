"""
tests/test_phase1.py
====================
Phase 1 validation tests for the Sustainable Route Recommendation System.

These tests verify the requirements listed in Section 4-F of the project spec:
  - Valid source/destination inputs are accepted.
  - Invalid inputs raise clear errors.
  - Disconnected routes are handled gracefully.
  - All computed metrics are non-negative.
  - The shortest-distance baseline truly minimises distance.
  - The fastest-time baseline truly minimises travel time.
  - Changing user preference recalculates scores and may change ranking.
  - Weights must sum to 1.0.

Run from the project root with the virtual environment activated:
  python -m pytest tests/ -v
  (or)
  python tests/test_phase1.py
"""

import sys
import os

# Allow imports from the project root regardless of how the test is invoked.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest

from road_network    import build_graph, validate_nodes, is_connected_path
from route_optimizer import (
    compute_all_routes,
    find_shortest_distance_route,
    find_fastest_time_route,
)
from sustainability  import score_routes, get_weights, PREFERENCE_PROFILES


class TestGraphConstruction(unittest.TestCase):
    """Tests that the graph is built correctly from simulation data."""

    def setUp(self):
        self.graph = build_graph()

    def test_graph_has_correct_nodes(self):
        expected = {"A", "B", "C", "D", "E", "F", "G", "H"}
        self.assertEqual(set(self.graph.nodes), expected)

    def test_edges_have_required_attributes(self):
        required_attrs = {"distance_km", "speed_kmh", "congestion",
                          "travel_time_h", "fuel_L", "co2_kg"}
        for u, v, data in self.graph.edges(data=True):
            for attr in required_attrs:
                self.assertIn(
                    attr, data,
                    msg=f"Edge ({u},{v}) missing attribute '{attr}'"
                )

    def test_all_metrics_non_negative(self):
        """Every edge attribute must be >= 0."""
        for u, v, data in self.graph.edges(data=True):
            for attr in ("distance_km", "travel_time_h", "fuel_L", "co2_kg", "congestion"):
                self.assertGreaterEqual(
                    data[attr], 0,
                    msg=f"Edge ({u},{v}) has negative {attr}: {data[attr]}"
                )


class TestInputValidation(unittest.TestCase):
    """Tests for valid and invalid source/destination inputs."""

    def setUp(self):
        self.graph = build_graph()

    def test_valid_nodes_accepted(self):
        # Should not raise
        validate_nodes(self.graph, "A", "H")

    def test_invalid_source_raises(self):
        with self.assertRaises(ValueError) as ctx:
            validate_nodes(self.graph, "Z", "H")
        self.assertIn("Z", str(ctx.exception))

    def test_invalid_destination_raises(self):
        with self.assertRaises(ValueError) as ctx:
            validate_nodes(self.graph, "A", "Z")
        self.assertIn("Z", str(ctx.exception))

    def test_same_source_and_destination_raises(self):
        with self.assertRaises(ValueError) as ctx:
            validate_nodes(self.graph, "A", "A")
        self.assertIn("A", str(ctx.exception))

    def test_connectivity_detected(self):
        graph = self.graph
        # A and H are connected in the simulated network
        self.assertTrue(is_connected_path(graph, "A", "H"))


class TestRouteMetrics(unittest.TestCase):
    """Tests that route metrics are computed correctly."""

    def setUp(self):
        self.graph  = build_graph()
        self.routes = compute_all_routes(self.graph, "A", "H")

    def test_at_least_one_route_found(self):
        self.assertGreater(len(self.routes), 0)

    def test_route_metrics_non_negative(self):
        """All route-level metrics must be non-negative."""
        for route in self.routes:
            for key in ("distance_km", "travel_time_min",
                        "fuel_L", "co2_kg", "avg_congestion"):
                self.assertGreaterEqual(
                    route[key], 0,
                    msg=f"Route {route['path_str']} has negative {key}"
                )

    def test_path_connects_source_to_destination(self):
        for route in self.routes:
            path = route["path"]
            self.assertEqual(path[0], "A")
            self.assertEqual(path[-1], "H")

    def test_no_duplicate_routes(self):
        path_strings = [r["path_str"] for r in self.routes]
        self.assertEqual(len(path_strings), len(set(path_strings)),
                         "Duplicate routes detected")

    def test_pollution_exposure_marked_as_future(self):
        """Pollution exposure must be None (future extension) for all routes."""
        for route in self.routes:
            self.assertIsNone(
                route.get("pollution_exposure"),
                msg="pollution_exposure should be None until Phase 2"
            )


class TestBaselines(unittest.TestCase):
    """
    Tests that the shortest-distance and fastest-time baselines
    truly minimise their respective metrics.
    """

    def setUp(self):
        graph        = build_graph()
        self.routes  = compute_all_routes(graph, "A", "H")
        self.shortest = find_shortest_distance_route(self.routes)
        self.fastest  = find_fastest_time_route(self.routes)

    def test_shortest_distance_is_minimum(self):
        min_dist = min(r["distance_km"] for r in self.routes)
        self.assertAlmostEqual(
            self.shortest["distance_km"], min_dist, places=5,
            msg="Shortest-distance baseline does not have the minimum distance"
        )

    def test_fastest_time_is_minimum(self):
        min_time = min(r["travel_time_h"] for r in self.routes)
        self.assertAlmostEqual(
            self.fastest["travel_time_h"], min_time, places=5,
            msg="Fastest-time baseline does not have the minimum travel time"
        )


class TestSustainabilityScoring(unittest.TestCase):
    """Tests for the sustainability scoring and preference system."""

    def setUp(self):
        graph        = build_graph()
        self.routes  = compute_all_routes(graph, "A", "H")

    def test_scores_are_in_valid_range(self):
        """All sustainability scores must be between 0 and 1 inclusive."""
        for pref in PREFERENCE_PROFILES:
            scored = score_routes(self.routes, pref)
            for route in scored:
                self.assertGreaterEqual(route["sustainability_score"], 0.0,
                                        msg=f"Score < 0 for {pref}")
                self.assertLessEqual(route["sustainability_score"], 1.0,
                                     msg=f"Score > 1 for {pref}")

    def test_preference_recalculates_scores(self):
        """
        Scores must differ across profiles when routes are not identical.
        Verify that changing preference re-ranks or at minimum re-scores routes.
        """
        scored_eco      = score_routes(self.routes, "eco")
        scored_fastest  = score_routes(self.routes, "fastest")

        eco_scores     = [r["sustainability_score"] for r in scored_eco]
        fastest_scores = [r["sustainability_score"] for r in scored_fastest]

        # Scores should not be identical across every route for different profiles
        self.assertNotEqual(
            eco_scores, fastest_scores,
            msg="Eco and Fastest profiles produced identical score lists"
        )

    def test_invalid_preference_raises(self):
        with self.assertRaises(ValueError):
            score_routes(self.routes, "teleport")

    def test_weights_must_sum_to_one(self):
        with self.assertRaises(ValueError):
            get_weights("fastest", custom_weights={
                "travel_time_min": 0.50,
                "fuel_L"         : 0.50,
                "co2_kg"         : 0.50,  # sums to 1.5
                "avg_congestion" : 0.00,
            })

    def test_custom_weights_accepted(self):
        """Valid custom weights should be accepted and produce a result."""
        custom = {
            "travel_time_min": 0.40,
            "fuel_L"         : 0.30,
            "co2_kg"         : 0.20,
            "avg_congestion" : 0.10,
        }
        scored = score_routes(self.routes, "fastest", custom_weights=custom)
        self.assertGreater(len(scored), 0)

    def test_routes_sorted_best_first(self):
        """Returned routes must be in descending score order."""
        for pref in PREFERENCE_PROFILES:
            scored = score_routes(self.routes, pref)
            scores = [r["sustainability_score"] for r in scored]
            self.assertEqual(
                scores, sorted(scores, reverse=True),
                msg=f"Routes not sorted best-first for preference '{pref}'"
            )


if __name__ == "__main__":
    print("Running Phase 1 validation tests...\n")
    loader  = unittest.TestLoader()
    suite   = loader.loadTestsFromModule(sys.modules[__name__])
    runner  = unittest.TextTestRunner(verbosity=2)
    result  = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
