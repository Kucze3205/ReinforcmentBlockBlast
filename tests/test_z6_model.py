"""
Testy `tools/z6_model.py` (#211): wzór na log-wiarygodność (M0/M1 to M2 z
p=0), podział uczące/testowe deterministyczny i stabilny, dopasowanie M1
zamkniętym wzorem daje rozkład prawdopodobieństwa.
"""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

from tools.z6_model import (
    N_TYPES,
    fit_m0,
    fit_m1,
    geometric_sum,
    is_test_id,
    loglik_rows,
    pi_batch,
    precompute_importance_samples,
    row_log_q,
)


def _fake_row(row_id, board, type_idx, playable):
    return {
        "id": row_id,
        "board": board,
        "type_idx": np.array(type_idx, dtype=int),
        "playable": playable,
    }


class TestGeometricSum(unittest.TestCase):
    def test_matches_closed_form(self):
        r = np.array([0.0, 0.3, 0.5, 0.9])
        for k in (1, 2, 3, 5):
            got = geometric_sum(r, k)
            want = np.array([sum(x ** m for m in range(k)) for x in r])
            np.testing.assert_allclose(got, want, atol=1e-12)

    def test_k_one_is_always_one(self):
        r = np.array([0.0, 0.5, 1.0])
        np.testing.assert_allclose(geometric_sum(r, 1), np.ones(3))


class TestSplitDeterministic(unittest.TestCase):
    def test_deterministic_and_stable(self):
        ids = ["cb91077/moves.jsonl#3", "4a1796f/chunk2_moves.jsonl#10", "0d96333/moves.jsonl#0"]
        for pair_id in ids:
            self.assertEqual(is_test_id(pair_id), is_test_id(pair_id))

    def test_roughly_twenty_percent(self):
        ids = [f"run/moves.jsonl#{i}" for i in range(2000)]
        frac = sum(1 for i in ids if is_test_id(i)) / len(ids)
        self.assertAlmostEqual(frac, 0.2, delta=0.03)


class TestFitM0M1(unittest.TestCase):
    def test_m0_matches_generator_weights(self):
        from generator import PIECE_TYPE_WEIGHTS
        w0 = fit_m0()
        self.assertAlmostEqual(w0.sum(), 1.0, places=10)
        expected = np.array(PIECE_TYPE_WEIGHTS, dtype=float)
        expected = expected / expected.sum()
        np.testing.assert_allclose(w0, expected)

    def test_m1_is_probability_distribution(self):
        rows = [
            _fake_row("a", None, [0, 1, 2], True),
            _fake_row("b", None, [1, 1, 3], True),
        ]
        w1 = fit_m1(rows)
        self.assertEqual(len(w1), N_TYPES)
        self.assertAlmostEqual(w1.sum(), 1.0, places=10)
        self.assertTrue((w1 > 0).all())

    def test_m1_favors_observed_types(self):
        rows = [_fake_row(str(i), None, [0, 0, 0], True) for i in range(20)]
        w1 = fit_m1(rows)
        self.assertEqual(np.argmax(w1), 0)


class TestLoglikReducesToM1AtPZero(unittest.TestCase):
    """M0/M1 są przypadkiem M2 z p=0 -- pi się nie liczy, wzór upraszcza się
    do log q(tacka), niezależnie od planszy (patrz docstring z6_model.py)."""

    def test_p_zero_matches_row_log_q(self):
        rows = [
            _fake_row("a", [[0] * 8 for _ in range(8)], [0, 1, 2], True),
            _fake_row("b", [[1] * 8 for _ in range(8)], [3, 4, 5], False),
        ]
        w = fit_m0()
        samples = precompute_importance_samples(rows, n_samples=20, seed=1)
        ll = loglik_rows(w, 0.0, 3, rows, samples)
        expected = row_log_q(w, rows)
        np.testing.assert_allclose(ll, expected, atol=1e-9)


class TestPiBatch(unittest.TestCase):
    def test_pi_between_zero_and_one(self):
        empty_board = [[0] * 8 for _ in range(8)]
        full_board = [[1] * 8 for _ in range(8)]
        rows = [
            _fake_row("empty", empty_board, [0, 0, 0], True),
            _fake_row("full", full_board, [0, 0, 0], False),
        ]
        w = fit_m0()
        samples = precompute_importance_samples(rows, n_samples=100, seed=2)
        pi = pi_batch(w, samples)
        self.assertTrue((pi >= 0).all() and (pi <= 1 + 1e-9).all())
        # plansza pusta: prawie na pewno da się coś ustawic; pełna: nigdy
        self.assertGreater(pi[0], pi[1])
        self.assertEqual(pi[1], 0.0)


if __name__ == "__main__":
    unittest.main()
