"""
Pole `reward` pliku wag N-tuple i suma ścieżki w `NTupleLookaheadPolicy` (#140).

Wagi `score` (także plik bez pola `reward`, sprzed #140) sumują po ścieżce
`gain`; wagi `survival` — liczbę postawień, bo tego sygnału się uczyły.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import policies
from game import Game
from ntuple import NTupleValue
from policies import NTupleLookaheadPolicy


class TestWeightsFileReward(unittest.TestCase):
    def test_file_without_reward_loads_as_score(self):
        data = NTupleValue().to_dict()
        del data["reward"]
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "old.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
            self.assertEqual(NTupleValue.load(path).reward, "score")

    def test_repo_root_weights_file_still_loads(self):
        # Plik z #126, zapisany przed polem `reward`.
        loaded = NTupleValue.load("ntuple-weights.json")
        self.assertEqual(loaded.reward, "score")

    def test_reward_round_trips(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "w.json")
            NTupleValue(reward="survival").save(path)
            self.assertEqual(NTupleValue.load(path).reward, "survival")

    def test_unknown_reward_rejected(self):
        with self.assertRaises(ValueError):
            NTupleValue(reward="lines")


class TestSurvivalPathSum(unittest.TestCase):
    def test_policy_path_key_follows_weights(self):
        self.assertEqual(NTupleLookaheadPolicy(NTupleValue())._path_key, "gain")
        self.assertEqual(NTupleLookaheadPolicy(NTupleValue(reward="survival"))._path_key, "placed")

    def test_beam_scores_count_placements_not_points(self):
        game = Game(seed=11)
        leaf = lambda board, combo, combo_counter: 0.0
        frontier, _ = policies._tray_beam_search(
            game.board, tuple(game.pieces), game.combo, game.combo_counter,
            None, beam=5, leaf_value=leaf, path_key="placed",
        )
        depth = sum(1 for p in game.pieces if p is not None)
        for state in frontier:
            self.assertEqual(state["placed"], depth)
            self.assertEqual(state["score"], depth)
            self.assertGreater(state["gain"], depth)  # punkty to nie postawienia

    def test_survival_weights_rank_by_placements_plus_leaf(self):
        # Zero wag: kazda pelna sekwencja tacki ma ten sam wynik (liczba postawien),
        # wiec o kolejnosci decyduje stabilne sortowanie, nie punkty.
        game = Game(seed=11)
        policy = NTupleLookaheadPolicy(NTupleValue(reward="survival"), samples=0)
        frontier, _ = policy._search(
            game.board, tuple(game.pieces), game.combo, game.combo_counter, policy.beam,
            root_actions=game.available_actions(),
        )
        self.assertEqual(len({s["score"] for s in frontier}), 1)
        score_policy = NTupleLookaheadPolicy(NTupleValue(), samples=0)
        score_frontier, _ = score_policy._search(
            game.board, tuple(game.pieces), game.combo, game.combo_counter, score_policy.beam,
            root_actions=game.available_actions(),
        )
        self.assertEqual([s["score"] for s in score_frontier], [s["gain"] for s in score_frontier])

    def test_survival_policy_plays_a_game(self):
        weights = NTupleValue.load("ntuple-weights.json").weights
        policy = NTupleLookaheadPolicy(NTupleValue(weights=weights, reward="survival"))
        game = Game(seed=3)
        policy.reset(3)
        steps = 0
        while not game.done and steps < 15:
            actions = game.available_actions()
            action = policy.act(game, actions)
            self.assertIn(action, actions)
            game.step(action)
            steps += 1
        self.assertGreater(steps, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
