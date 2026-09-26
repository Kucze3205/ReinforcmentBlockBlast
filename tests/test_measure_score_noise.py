"""
Testy `tools/measure_score_noise.py` (#101): statystyki, korelacje, tabela
"partii na kandydata". Szybkie — nie rozgrywaja pelnych 150 partii
`lookahead`; pelny pomiar jest osobnym, recznym uruchomieniem opisanym w
`docs/szum-oceny-kandydata.md`.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from board import Board
from pieces import Piece
from tools.measure_score_noise import (
    _any_action_would_clear,
    combo_summary,
    dump_series,
    dump_series_detailed,
    games_per_candidate_table,
    load_bench_seeds,
    load_seeds_from_file,
    play_series,
    play_series_detailed,
    spearman,
    summarize,
)
from tools.tune_weights import training_seeds


class TestSummarize(unittest.TestCase):
    def test_basic_stats(self):
        stats = summarize([2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0])
        self.assertEqual(stats["n"], 8)
        self.assertAlmostEqual(stats["mean"], 5.0)
        self.assertAlmostEqual(stats["sigma"], 2.0)
        self.assertAlmostEqual(stats["cv"], 0.4)
        self.assertAlmostEqual(stats["sem"], round(2.0 / (8 ** 0.5), 2), places=4)

    def test_zero_mean_no_division_error(self):
        stats = summarize([0.0, 0.0, 0.0])
        self.assertIsNone(stats["cv"])
        self.assertIsNone(stats["sem_pct_of_mean"])


class TestSpearman(unittest.TestCase):
    def test_perfect_monotonic_relationship(self):
        xs = [1, 2, 3, 4, 5]
        ys = [10, 20, 30, 40, 50]
        self.assertAlmostEqual(spearman(xs, ys), 1.0)

    def test_handles_ties(self):
        xs = [1, 1, 2, 3]
        ys = [1, 1, 2, 3]
        self.assertAlmostEqual(spearman(xs, ys), 1.0)


class TestGamesPerCandidateTable(unittest.TestCase):
    def test_sem_shrinks_with_more_games(self):
        rows = games_per_candidate_table(sigma=100.0, mean=1000.0, counts=(6, 16, 32, 64))
        sems = [r["sem"] for r in rows]
        self.assertEqual(sems, sorted(sems, reverse=True))
        for row in rows:
            expected_sem = 100.0 / (row["n_games"] ** 0.5)
            self.assertAlmostEqual(row["sem"], round(expected_sem, 2))
            self.assertAlmostEqual(
                row["min_detectable_diff"], round(2.0 * (2.0 ** 0.5) * expected_sem, 2)
            )


class TestPlaySeries(unittest.TestCase):
    def test_disjoint_training_seeds_and_matching_lengths(self):
        bench_seeds, move_cap = load_bench_seeds("bench/config.json")
        seeds = training_seeds(5, bench_seeds, salt=101)
        self.assertFalse(set(seeds) & set(bench_seeds))

        scores, survivals, capped = play_series("heuristic", None, seeds, move_cap)
        self.assertEqual(len(scores), 5)
        self.assertEqual(len(survivals), 5)
        self.assertEqual(len(capped), 5)
        self.assertTrue(all(isinstance(s, (int, float)) for s in scores))
        self.assertTrue(all(p >= 0 for p in survivals))
        self.assertTrue(all(isinstance(c, bool) for c in capped))


class TestLoadSeedsFromFile(unittest.TestCase):
    def test_reads_list_and_truncates_to_n_games(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as fh:
            json.dump([11, 22, 33, 44, 55], fh)
            path = fh.name
        try:
            seeds = load_seeds_from_file(path, 3)
            self.assertEqual(seeds, [11, 22, 33])
        finally:
            os.remove(path)

    def test_rejects_non_list(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as fh:
            json.dump({"seeds": [1, 2, 3]}, fh)
            path = fh.name
        try:
            with self.assertRaises(ValueError):
                load_seeds_from_file(path, 3)
        finally:
            os.remove(path)

    def test_uses_bench_seeds_fixed_file(self):
        bench_seeds, _move_cap = load_bench_seeds("bench/config.json")
        seeds = load_seeds_from_file("bench/seeds_fixed.json", 5)
        self.assertEqual(seeds, bench_seeds[:5])


class TestDumpSeries(unittest.TestCase):
    def test_dumps_seed_score_survival_capped_rows(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as fh:
            path = fh.name
        try:
            dump_series(path, [1, 2], [100, 200], [10, 20], [False, True])
            with open(path, encoding="utf-8") as fh:
                rows = json.load(fh)
            self.assertEqual(rows, [
                {"seed": 1, "score": 100, "survival": 10, "capped": False},
                {"seed": 2, "score": 200, "survival": 20, "capped": True},
            ])
        finally:
            os.remove(path)


class TestAnyActionWouldClear(unittest.TestCase):
    def test_detects_clearing_action_among_several(self):
        board = Board()
        for x in range(Board.WIDTH - 1):
            board.grid[0][x] = 1  # brakuje jednej komorki do pelnego wiersza 0
        piece = Piece([[1]], "single", 0)
        pieces = [piece]
        clearing_action = (0, Board.WIDTH - 1, 0)
        non_clearing_action = (0, 0, 5)
        self.assertTrue(
            _any_action_would_clear(board, pieces, [non_clearing_action, clearing_action])
        )

    def test_no_clearing_action_available(self):
        board = Board()
        piece = Piece([[1]], "single", 0)
        pieces = [piece]
        actions = [(0, 0, 0), (0, 1, 1)]
        self.assertFalse(_any_action_would_clear(board, pieces, actions))


class TestPlaySeriesDetailed(unittest.TestCase):
    def test_placement_plus_clear_equals_score_and_breaks_are_categorized(self):
        bench_seeds, move_cap = load_bench_seeds("bench/config.json")
        seeds = training_seeds(4, bench_seeds, salt=101)
        records = play_series_detailed("heuristic", None, seeds, move_cap)
        self.assertEqual(len(records), 4)
        for r in records:
            self.assertEqual(r["placement_points"] + r["clear_points"], r["score"])
            self.assertGreaterEqual(r["clear_points"], 0)
            self.assertEqual(r["breaks"], len(r["chain_lengths"]))
            self.assertEqual(r["breaks"], r["breaks_no_legal_clear"] + r["breaks_policy_choice"])
            self.assertGreaterEqual(r["unresolved_chain_at_end"], 0)
            self.assertGreaterEqual(r["max_combo"], 0)
            if r["clears"] == 0:
                self.assertIsNone(r["mean_combo_at_clear"])


class TestComboSummary(unittest.TestCase):
    def test_aggregates_percentages_causes_and_chain_distribution(self):
        records = [
            {
                "score": 100, "placement_points": 40, "clear_points": 60,
                "clears": 2, "max_combo": 3, "mean_combo_at_clear": 2.0,
                "breaks": 1, "breaks_no_legal_clear": 1, "breaks_policy_choice": 0,
                "chain_lengths": [3], "unresolved_chain_at_end": 0,
            },
            {
                "score": 50, "placement_points": 20, "clear_points": 30,
                "clears": 1, "max_combo": 1, "mean_combo_at_clear": 1.0,
                "breaks": 0, "breaks_no_legal_clear": 0, "breaks_policy_choice": 0,
                "chain_lengths": [], "unresolved_chain_at_end": 1,
            },
        ]
        summary = combo_summary(records)
        self.assertEqual(summary["total_score"], 150)
        self.assertAlmostEqual(summary["placement_points_pct"], 100.0 * 60 / 150)
        self.assertAlmostEqual(summary["clear_points_pct"], 100.0 * 90 / 150)
        self.assertEqual(summary["break_causes"]["total_breaks"], 1)
        self.assertEqual(summary["break_causes"]["no_legal_clear"], 1)
        self.assertEqual(summary["break_causes"]["policy_choice"], 0)
        self.assertEqual(summary["chain_length"]["n_broken"], 1)
        self.assertEqual(summary["chain_length"]["n_censored_at_game_end"], 1)
        self.assertEqual(summary["chain_length"]["max"], 3)
        self.assertAlmostEqual(summary["mean_combo_at_clear_pooled"], 5.0 / 3, places=4)

    def test_zero_breaks_gives_none_percentages(self):
        records = [{
            "score": 10, "placement_points": 10, "clear_points": 0,
            "clears": 0, "max_combo": 0, "mean_combo_at_clear": None,
            "breaks": 0, "breaks_no_legal_clear": 0, "breaks_policy_choice": 0,
            "chain_lengths": [], "unresolved_chain_at_end": 0,
        }]
        summary = combo_summary(records)
        self.assertIsNone(summary["break_causes"]["no_legal_clear_pct"])
        self.assertIsNone(summary["mean_combo_at_clear_pooled"])
        self.assertIsNone(summary["chain_length"]["median"])


class TestDumpSeriesDetailed(unittest.TestCase):
    def test_round_trips_full_records(self):
        records = [{"seed": 1, "score": 100, "chain_lengths": [2, 3]}]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as fh:
            path = fh.name
        try:
            dump_series_detailed(path, records)
            with open(path, encoding="utf-8") as fh:
                loaded = json.load(fh)
            self.assertEqual(loaded, records)
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
