"""
Testy `tools/z6_testy.py` (#182): dystrybuanta chi-kwadrat bez scipy, i grywalność
całej tacki z czyszczeniem linii między postawieniami (dlaczego kolejność klocków
w tacce ma znaczenie -- kluczowe dla testów (c)/(d)).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

from tools.z6_testy import (
    chi2_sf,
    poisson_binomial_test,
    tray_playable,
)


class TestChi2Sf(unittest.TestCase):
    def test_matches_known_critical_values(self):
        # progi tablicowe dla alpha=0.05
        cases = [
            (3.841, 1),
            (23.685, 14),
            (55.758, 40),
        ]
        for x, df in cases:
            self.assertAlmostEqual(chi2_sf(x, df), 0.05, places=3)

    def test_zero_statistic_gives_p_one(self):
        self.assertEqual(chi2_sf(0.0, 10), 1.0)

    def test_monotonically_decreasing_in_statistic(self):
        p1 = chi2_sf(5.0, 10)
        p2 = chi2_sf(20.0, 10)
        self.assertGreater(p1, p2)


class TestTrayPlayable(unittest.TestCase):
    def test_empty_board_always_playable(self):
        board = [[0] * 8 for _ in range(8)]
        shapes = [[[1]], [[1, 1]], [[1, 1, 1]]]
        self.assertTrue(tray_playable(board, shapes))

    def test_full_board_never_playable(self):
        board = [[1] * 8 for _ in range(8)]
        shapes = [[[1]], [[1, 1]], [[1, 1, 1]]]
        self.assertFalse(tray_playable(board, shapes))

    def test_order_matters_because_of_line_clear(self):
        # Rzad 0 ma 7 z 8 komorek zajetych, reszta planszy w calosci zajeta.
        # Jedyny ruch mozliwy na starcie: 1x1 w wolna komorke (7,0) - to czysci
        # caly rzad 0. Dopiero PO tym czyszczeniu miesci sie tam belka 5 i belka 2.
        # Statyczne (bez czyszczenia) sprawdzenie trzech rozlacznych miejsc na
        # niezmienionej planszy nie znalazloby zadnego miejsca na belke 5 ani 2.
        board = [[1] * 8 for _ in range(8)]
        board[0] = [1, 1, 1, 1, 1, 1, 1, 0]
        shapes = [[[1]], [[1, 1, 1, 1, 1]], [[1, 1]]]
        self.assertTrue(tray_playable(board, shapes))

    def test_unplayable_without_the_enabling_clear(self):
        # Jak wyzej, ale bez luki w rzedzie 0 (plansza w calosci zajeta) -
        # nic sie nie miesci, bo nic nie da sie w ogole postawic jako pierwsze.
        board = [[1] * 8 for _ in range(8)]
        shapes = [[[1]], [[1, 1, 1, 1, 1]], [[1, 1]]]
        self.assertFalse(tray_playable(board, shapes))


class TestPoissonBinomialTest(unittest.TestCase):
    def test_expected_matches_sum_of_probs(self):
        probs = [0.5, 0.5, 0.5, 0.5]
        result = poisson_binomial_test(probs, observed=2)
        self.assertAlmostEqual(result["expected_playable_h0"], 2.0)
        self.assertEqual(result["n"], 4)

    def test_extreme_observation_gives_small_one_sided_p(self):
        probs = [0.1] * 20
        result = poisson_binomial_test(probs, observed=20)
        self.assertLess(result["p_value_one_sided_ge"], 0.01)

    def test_expected_observation_gives_large_p(self):
        probs = [0.5] * 20
        result = poisson_binomial_test(probs, observed=10)
        self.assertGreater(result["p_value_two_sided"], 0.5)


if __name__ == "__main__":
    unittest.main()
