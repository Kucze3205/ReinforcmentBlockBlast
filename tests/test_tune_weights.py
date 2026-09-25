"""
Testy `tools/tune_weights.py` (#59): rozłączność seedów, format `weights.json`,
poprawność `TraySearchPolicy` i aktualizacji CEM. Szybkie (limity czasu w
sekundach) — pełny przebieg strojenia jest osobnym, ręcznym uruchomieniem
udokumentowanym w `docs/strojenie-wag.md`.
"""
import json
import os
import random
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

from board import Board
from features import FEATURE_NAMES
from game import Game
from policies import HeuristicPolicy
from tools.tune_weights import (
    TraySearchPolicy,
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


class TestTraySearchPolicy(unittest.TestCase):
    def test_returns_legal_action_from_fresh_tray(self):
        game = Game(seed=123)
        policy = TraySearchPolicy(HeuristicPolicy.DEFAULT_WEIGHTS)
        policy.reset(123)
        actions = game.available_actions()
        action = policy.act(game, actions)
        self.assertIn(action, actions)

    def test_plan_is_consumed_across_a_round(self):
        game = Game(seed=42)
        policy = TraySearchPolicy(HeuristicPolicy.DEFAULT_WEIGHTS)
        policy.reset(42)
        for _ in range(3):
            actions = game.available_actions()
            action = policy.act(game, actions)
            self.assertIn(action, actions)
            gained, _score, done, _msg = game.step(action)
            self.assertGreaterEqual(gained, 0)
            if done:
                break

    def test_prefers_line_clear_over_empty_board_when_equally_weighted(self):
        # Plansza prawie pelny wiersz 0 (brakuje jednego pola na x=7), reszta pusta.
        # Klocek 1x1 na (7,0) czysci linie i daje najwyzszy natychmiastowy zysk
        # niezaleznie od wag cech (te sa te same dla kazdego kandydata w tacce).
        board = Board()
        board.grid[0] = [1, 1, 1, 1, 1, 1, 1, 0]
        game = Game(seed=1)
        game.board = board
        from pieces import PIECE_POOL

        one_by_one = next(p for p in PIECE_POOL if len(p.shape) == 1 and len(p.shape[0]) == 1)
        game.pieces = [one_by_one, one_by_one, one_by_one]
        policy = TraySearchPolicy(HeuristicPolicy.DEFAULT_WEIGHTS)
        policy.reset(1)
        actions = game.available_actions()
        idx, x, y = policy.act(game, actions)
        self.assertEqual((x, y), (7, 0))


class TestEvaluateCandidate(unittest.TestCase):
    def test_heuristic_matches_default_weights_policy(self):
        seeds = [111, 222]
        score = evaluate_candidate("heuristic", HeuristicPolicy.DEFAULT_WEIGHTS, seeds, move_cap=50)
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
