"""
Test regresji dla #123: wpiecie ntuple.py jako alternatywnego zrodla wartosci
liscia nie zmienia ANI JEDNEGO ruchu ramienia `lookahead:weights.json`.

`tests/fixtures/lookahead_regression.json` zostal przechwycony na 20 seedach
bench/seeds_fixed.json PRZED modyfikacja policies.py (przed dodaniem
NTupleLookaheadPolicy i haka `_leaf_value` w LookaheadPolicy). Ten test
odtwarza te sama gre na biezacym kodzie i porownuje sekwencje znak w znak —
to jest ramie odniesienia kazdego przyszlego pomiaru (#123, kryterium
akceptacji).
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmark import load_tuned_weights
from game import Game
from policies import LookaheadPolicy

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "lookahead_regression.json")
MOVE_CAP = 60


def play(policy, seed):
    game = Game(seed=seed)
    policy.reset(seed)
    moves = []
    while not game.done and len(moves) < MOVE_CAP:
        actions = game.available_actions()
        if not actions:
            break
        action = policy.act(game, actions)
        moves.append(list(action))
        game.step(action)
    return moves


class TestLookaheadWeightsRegression(unittest.TestCase):
    def test_matches_pre_change_move_sequences_on_twenty_seeds(self):
        with open(FIXTURE_PATH, encoding="utf-8") as fh:
            expected = json.load(fh)
        self.assertGreaterEqual(len(expected), 20)

        weights = load_tuned_weights("weights.json")
        policy = LookaheadPolicy(weights=weights)
        for seed_str, expected_moves in expected.items():
            actual = play(policy, int(seed_str))
            self.assertEqual(actual, expected_moves, "seed=%s" % seed_str)


if __name__ == "__main__":
    unittest.main(verbosity=2)
