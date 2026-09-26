"""
Testy `tools/measure_score_noise.py` (#101): statystyki, korelacje, tabela
"partii na kandydata". Szybkie — nie rozgrywaja pelnych 150 partii
`lookahead`; pelny pomiar jest osobnym, recznym uruchomieniem opisanym w
`docs/szum-oceny-kandydata.md`.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.measure_score_noise import (
    games_per_candidate_table,
    load_bench_seeds,
    play_series,
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

        scores, survivals = play_series("heuristic", None, seeds, move_cap)
        self.assertEqual(len(scores), 5)
        self.assertEqual(len(survivals), 5)
        self.assertTrue(all(isinstance(s, (int, float)) for s in scores))
        self.assertTrue(all(p >= 0 for p in survivals))


if __name__ == "__main__":
    unittest.main()
