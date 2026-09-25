"""
Testy `tools/tune_weights.py` (#59, #77): rozłączność seedów, format
`weights.json`, `build_policy` i aktualizacji CEM. Szybkie (limity czasu w
sekundach) — pełny przebieg strojenia jest osobnym, ręcznym uruchomieniem
udokumentowanym w `docs/strojenie-wag.md`.

`TrayPolicy` sama w sobie (przeszukanie tacki, brak mutacji gry, kolejność
klocków ma znaczenie) ma dedykowane testy w `tests/test_tray_policy.py` —
tu sprawdzamy tylko, że `build_policy("tray", ...)` faktycznie jej używa.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

from features import FEATURE_NAMES
from policies import HeuristicPolicy, TrayPolicy
from tools.tune_weights import (
    build_policy,
    evaluate_candidate,
    main as tune_main,
    training_seeds,
    update_distribution,
)


class TestTrainingSeeds(unittest.TestCase):
    def test_disjoint_from_forbidden_set(self):
        forbidden = list(range(1, 51))
        seeds = training_seeds(20, forbidden, salt=1)
        self.assertEqual(len(seeds), 20)
        self.assertEqual(len(set(seeds)), 20)
        self.assertFalse(set(seeds) & set(forbidden))

    def test_deterministic_for_same_salt(self):
        forbidden = [1259289227, 1358106528]
        a = training_seeds(10, forbidden, salt=7)
        b = training_seeds(10, forbidden, salt=7)
        self.assertEqual(a, b)

    def test_different_salts_differ(self):
        forbidden = []
        a = training_seeds(10, forbidden, salt=1)
        b = training_seeds(10, forbidden, salt=2)
        self.assertNotEqual(a, b)

    def test_disjoint_from_real_bench_seeds_file(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "bench", "seeds_fixed.json"), encoding="utf-8") as fh:
            bench_seeds = json.load(fh)
        seeds = training_seeds(30, bench_seeds, salt=0)
        self.assertFalse(set(seeds) & set(bench_seeds))


class TestUpdateDistribution(unittest.TestCase):
    def test_mean_matches_elite_average(self):
        elite = [(0.0, 2.0), (2.0, 4.0), (4.0, 6.0)]
        mean, std = update_distribution(elite)
        self.assertAlmostEqual(mean[0], 2.0)
        self.assertAlmostEqual(mean[1], 4.0)
        self.assertGreater(std[0], 0)

    def test_std_has_floor_for_identical_elite(self):
        elite = [(1.0, 1.0), (1.0, 1.0)]
        _mean, std = update_distribution(elite)
        self.assertGreaterEqual(std[0], 0.05)


class TestBuildPolicy(unittest.TestCase):
    def test_heuristic_uses_heuristic_policy_with_given_weights(self):
        weights = tuple(2.0 for _ in FEATURE_NAMES)
        policy = build_policy("heuristic", weights)
        self.assertIsInstance(policy, HeuristicPolicy)
        self.assertEqual(policy.weights, weights)

    def test_tray_uses_policies_tray_policy_with_given_weights(self):
        weights = tuple(1.5 for _ in FEATURE_NAMES)
        policy = build_policy("tray", weights)
        self.assertIsInstance(policy, TrayPolicy)
        self.assertEqual(policy.weights, weights)

    def test_unknown_policy_raises(self):
        with self.assertRaises(ValueError):
            build_policy("nope", HeuristicPolicy.DEFAULT_WEIGHTS)


class TestEvaluateCandidate(unittest.TestCase):
    def test_heuristic_matches_default_weights_policy(self):
        seeds = [111, 222]
        score = evaluate_candidate("heuristic", HeuristicPolicy.DEFAULT_WEIGHTS, seeds, move_cap=50)
        self.assertIsInstance(score, (int, float))

    def test_tray_policy_evaluates_via_policies_tray_policy(self):
        seeds = [111, 222]
        score = evaluate_candidate("tray", TrayPolicy.DEFAULT_WEIGHTS, seeds, move_cap=50)
        self.assertIsInstance(score, (int, float))


class TestMainProducesWeightsFile(unittest.TestCase):
    def test_writes_weights_json_with_expected_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_path = os.path.join(tmp, "weights.json")
            root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            cwd = os.getcwd()
            os.chdir(root)
            try:
                tune_main([
                    "--policy", "heuristic",
                    "--minutes", "0.02",
                    "--games-per-candidate", "2",
                    "--population", "2",
                    "--elite", "1",
                    "--seed", "5",
                    "--out", out_path,
                ])
            finally:
                os.chdir(cwd)
            with open(out_path, encoding="utf-8") as fh:
                record = json.load(fh)
            self.assertEqual(record["policy"], "heuristic")
            self.assertEqual(record["feature_names"], list(FEATURE_NAMES))
            self.assertEqual(len(record["weights"]), len(FEATURE_NAMES))
            self.assertIn("log", record)


if __name__ == "__main__":
    unittest.main(verbosity=2)
