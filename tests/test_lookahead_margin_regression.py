"""
Test regresji dla #210: dodanie opcji `margin` (domyslnie wylaczonej, `None`) do
`LookaheadPolicy`/`NTupleLookaheadPolicy._distinct_first_actions` nie zmienia ani
jednego ruchu domyslnej specyfikacji `lookahead-ntuple:<plik>@beam=128` (rekord #201).

`tests/fixtures/lookahead_margin_regression.json` zostal przechwycony na 50 seedach
`bench/seeds_fixed.json` PRZED dodaniem `margin` do `policies.py`. Ten test odtwarza
te same partie na biezacym kodzie i porownuje sekwencje znak w znak.
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmark import build_policy, load_config

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "lookahead_margin_regression.json")
SPEC = "lookahead-ntuple:ntuple/survival-adcga16-800k.json@beam=128"
MOVE_CAP = 60


def play(policy, seed):
    from game import Game

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


class TestLookaheadMarginRegression(unittest.TestCase):
    def test_default_spec_matches_pre_margin_move_sequences_on_fifty_seeds(self):
        with open(FIXTURE_PATH, encoding="utf-8") as fh:
            expected = json.load(fh)
        self.assertGreaterEqual(len(expected), 50)

        config = load_config("bench/config.json")
        policy = build_policy(SPEC, config)
        self.assertIsNone(policy.margin, "domyslne margin musi zostac None")
        for seed_str, expected_moves in expected.items():
            actual = play(policy, int(seed_str))
            self.assertEqual(actual, expected_moves, "seed=%s" % seed_str)


if __name__ == "__main__":
    unittest.main(verbosity=2)
