"""
#186: generator.py losuje typ kanoniczny wg wag zmierzonych z mostu, nie 1/15.
Wagi i metoda: docs/generator-wagi-typow.md, dane: docs/data/z6-pary.json.
"""
import math
import os
import sys
import unittest
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from generator import Generator, PIECE_TYPE_WEIGHTS
from pieces import CANONICAL_TYPES, PIECE_TYPES

N_DRAWS = 120000
SEED = 20260928


class TestWeightedTypeSampling(unittest.TestCase):
    def test_frequencies_match_calibrated_weights(self):
        gen = Generator(SEED)
        counts = Counter()
        for _ in range(N_DRAWS):
            counts[gen._next_piece().type_index] += 1

        total_weight = sum(PIECE_TYPE_WEIGHTS)
        for t, (name, _) in enumerate(CANONICAL_TYPES):
            expected_p = PIECE_TYPE_WEIGHTS[t] / total_weight
            expected = expected_p * N_DRAWS
            std = math.sqrt(N_DRAWS * expected_p * (1 - expected_p))
            observed = counts.get(t, 0)
            # 6 odchyleń standardowych: przy 15 typach i jednym uruchomieniu
            # testu szansa fałszywego alarmu jest znikoma, a i tak wykrywa
            # pomyłkę rzędu "1/15 zamiast wagi" (odchylenie o dziesiątki std).
            self.assertLess(
                abs(observed - expected), 6 * std,
                f"typ {name}: obs={observed} exp={expected:.1f} std={std:.1f}",
            )

    def test_orientation_within_type_stays_uniform(self):
        # Orientacja pozostaje 1/n (Cel #186 - zmieniają się tylko wagi typów).
        gen = Generator(SEED)
        pose_counts = Counter()
        for _ in range(N_DRAWS):
            pose_counts[gen._next_piece().index] += 1

        # corner5 (4 poz, waga umiarkowana) - poz powinny być ~równe między sobą.
        type_index = next(i for i, (n, _) in enumerate(CANONICAL_TYPES) if n == "corner5")
        pose_indices = PIECE_TYPES[type_index]
        counts = [pose_counts.get(i, 0) for i in pose_indices]
        mean = sum(counts) / len(counts)
        for c in counts:
            self.assertLess(abs(c - mean) / mean, 0.15)

    def test_same_seed_gives_same_sequence(self):
        a = [gen_piece.name for gen_piece in _draw_many(Generator(7), 5000)]
        b = [gen_piece.name for gen_piece in _draw_many(Generator(7), 5000)]
        self.assertEqual(a, b)


def _draw_many(gen, n):
    return [gen._next_piece() for _ in range(n)]


if __name__ == "__main__":
    unittest.main()
