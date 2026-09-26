import random
import unittest

from board import Board
from features import _empty_regions, _row_bits
from pieces import PIECE_POOL
from game import Game
from tools.measure_terminal_state import (
    analyze_game,
    can_place_any_on,
    cliffs_delta,
    connected_empty_regions,
    distribution_summary,
    escape_stats,
    feature_k_vs_random,
    piece_type_distribution,
    summarize_terminal_board,
)
from policies import LookaheadPolicy


def _piece_by_name(name):
    for piece in PIECE_POOL:
        if piece.name == name:
            return piece
    raise KeyError(name)


class TestCanPlaceAnyOn(unittest.TestCase):
    def test_full_board_has_no_legal_move(self):
        board = Board()
        board.grid = [[1] * Board.WIDTH for _ in range(Board.HEIGHT)]
        self.assertFalse(can_place_any_on(board, [_piece_by_name("1x1")]))

    def test_empty_board_has_legal_move(self):
        board = Board()
        self.assertTrue(can_place_any_on(board, [_piece_by_name("1x1")]))

    def test_none_slots_are_skipped(self):
        board = Board()
        board.grid = [[1] * Board.WIDTH for _ in range(Board.HEIGHT)]
        self.assertFalse(can_place_any_on(board, [None, None]))


class TestConnectedEmptyRegions(unittest.TestCase):
    def test_two_separate_regions(self):
        grid = [[1] * Board.WIDTH for _ in range(Board.HEIGHT)]
        grid[0][0] = 0
        grid[0][1] = 0
        grid[7][7] = 0
        sizes = connected_empty_regions(grid)
        self.assertEqual(sorted(sizes), [1, 2])

    def test_fully_empty_board_is_one_region(self):
        grid = [[0] * Board.WIDTH for _ in range(Board.HEIGHT)]
        sizes = connected_empty_regions(grid)
        self.assertEqual(sizes, [Board.WIDTH * Board.HEIGHT])

    def test_fully_occupied_board_has_no_regions(self):
        grid = [[1] * Board.WIDTH for _ in range(Board.HEIGHT)]
        self.assertEqual(connected_empty_regions(grid), [])

    def test_region_count_matches_features_empty_regions(self):
        rng = random.Random(42)
        for _ in range(20):
            grid = [[1 if rng.random() < 0.55 else 0 for _ in range(Board.WIDTH)] for _ in range(Board.HEIGHT)]
            rows = [_row_bits(row) for row in grid]
            expected_count = _empty_regions(rows)
            self.assertEqual(len(connected_empty_regions(grid)), expected_count)


class TestCliffsDelta(unittest.TestCase):
    def test_fully_separated_is_plus_one(self):
        self.assertEqual(cliffs_delta([10, 11, 12], [1, 2, 3]), 1.0)

    def test_fully_separated_other_direction_is_minus_one(self):
        self.assertEqual(cliffs_delta([1, 2, 3], [10, 11, 12]), -1.0)

    def test_identical_distributions_is_zero(self):
        self.assertEqual(cliffs_delta([5, 5, 5], [5, 5, 5]), 0.0)

    def test_empty_input_is_none(self):
        self.assertIsNone(cliffs_delta([], [1, 2]))


class TestDistributionSummary(unittest.TestCase):
    def test_basic_stats(self):
        summary = distribution_summary([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        self.assertEqual(summary["n"], 10)
        self.assertAlmostEqual(summary["median"], 5.5)

    def test_empty_is_none(self):
        self.assertIsNone(distribution_summary([]))


class TestAggregationOnSyntheticRecords(unittest.TestCase):
    """(a)/(b)/(c)/(d): agregacja na recznie zbudowanych rekordach, bez rozgrywania partii."""

    def test_summarize_terminal_board_excludes_capped(self):
        records = [
            {"capped": False, "terminal_occupied_cells": 40, "terminal_empty_regions": 2, "terminal_largest_empty_region": 10},
            {"capped": False, "terminal_occupied_cells": 50, "terminal_empty_regions": 3, "terminal_largest_empty_region": 6},
            {"capped": True},
        ]
        summary = summarize_terminal_board(records)
        self.assertEqual(summary["n"], 2)
        self.assertEqual(summary["n_excluded_capped_or_empty"], 1)
        self.assertEqual(summary["occupied_cells"]["median"], 45)

    def test_piece_type_distribution_dominant(self):
        records = [
            {"terminal_piece_types": ["square2", "beam3"]},
            {"terminal_piece_types": ["square2"]},
            {"terminal_piece_types": ["square2", "square2"]},
        ]
        dist = piece_type_distribution(records)
        self.assertEqual(dist["total"], 5)
        self.assertEqual(dist["dominant"], "square2")
        self.assertAlmostEqual(dist["dominant_pct"], 80.0)

    def test_feature_k_vs_random_separates_when_clearly_different(self):
        records = [
            {"feature_at_k": {"1": (60, 0, 0, 0, 0, 0)}, "feature_random": (10, 0, 0, 0, 0, 0)},
            {"feature_at_k": {"1": (58, 0, 0, 0, 0, 0)}, "feature_random": (12, 0, 0, 0, 0, 0)},
            {"feature_at_k": {"1": None}, "feature_random": (11, 0, 0, 0, 0, 0)},
        ]
        result = feature_k_vs_random(records, feature_index=0, k=1)
        self.assertEqual(result["n_k"], 2)
        self.assertEqual(result["n_random"], 3)
        self.assertEqual(result["cliffs_delta"], 1.0)

    def test_escape_stats_forced_vs_choice(self):
        records = [
            {"escape_window": [{"pos_from_end": 0, "escapable": False}, {"pos_from_end": 1, "escapable": True}]},
            {"escape_window": [{"pos_from_end": 0, "escapable": False}, {"pos_from_end": 1, "escapable": True}]},
            {"escape_window": [{"pos_from_end": 0, "escapable": True}]},
        ]
        stats = escape_stats(records)
        self.assertEqual(stats[0]["n"], 3)
        self.assertAlmostEqual(stats[0]["forced_pct"], 200 / 3, places=1)
        self.assertEqual(stats[1]["n"], 2)
        self.assertAlmostEqual(stats[1]["policy_choice_pct"], 100.0)


class TestAnalyzeGameInvariant(unittest.TestCase):
    """Inwariant kryterium akceptacji: stan terminalny naprawde nie ma legalnego ruchu."""

    def test_terminal_state_has_no_legal_move(self):
        """Odtwarza partie niezaleznie od `tools.measure_terminal_state` i sprawdza
        wprost `can_place_any_on(game.board, game.pieces)` na koncowym stanie."""
        policy = LookaheadPolicy()
        for seed in (1259289227, 1358106528, 601855227):
            policy.reset(seed)
            game = Game(seed=seed)
            while not game.done and game.placements < 2000:
                actions = game.available_actions()
                if not actions:
                    break
                game.step(policy.act(game, actions))
            self.assertLess(game.placements, 2000, f"seed {seed}: gra ucieta sufitem, nie testuje smierci")
            self.assertFalse(can_place_any_on(game.board, game.pieces))

            result = analyze_game(policy, seed, move_cap=2000)
            self.assertFalse(result["capped"])
            self.assertIn("terminal_occupied_cells", result)


if __name__ == "__main__":
    unittest.main()
