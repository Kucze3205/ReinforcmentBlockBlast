"""
Testy parametru `gain_weight` (punkty w składniku ścieżki) w `NTupleLookaheadPolicy` (#248).
"""
import faulthandler
import json
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import benchmark
import policies
from game import Game
from ntuple import NTupleValue
from policies import NTupleLookaheadPolicy

WEIGHTS = "ntuple/survival-adce-400k.json"

# Wyniki `complete=1`, `samples=0`, sufit 4000 postawień, 5 pierwszych seedów stałych,
# waga `ntuple/survival-adce-400k.json` — zmierzone na kodzie sprzed #248 (`bench/240-complete.json`
# nie niesie wyników per seed).
BASELINE_SEEDS = [1259289227, 1358106528, 1524307444, 601855227, 274288237]
BASELINE_BEAM8_SCORES = [478518, 411769, 413278, 372386, 495054]
BASELINE_BEAM128_SCORES = [568704, 587729, 575926, 527261, 630016]


def _zero_policy(**kw):
    kw.setdefault("samples", 0)
    return NTupleLookaheadPolicy(NTupleValue(reward="survival"), **kw)


def _midgame(seed, moves):
    """Gra po `moves` postawieniach polityki z gwarancją tacki (wagi z pliku, wiązka 4)."""
    game = Game(seed=seed)
    pol = NTupleLookaheadPolicy(NTupleValue.load(WEIGHTS), beam=4, samples=0, complete=1)
    for _ in range(moves):
        game.step(pol.act(game, game.available_actions()))
    return game


class GainWeightTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        faulthandler.dump_traceback_later(1500, exit=True)

    @classmethod
    def tearDownClass(cls):
        faulthandler.cancel_dump_traceback_later()

    def test_param_is_known_and_parsed(self):
        self.assertIn("gain_weight", benchmark.NTUPLE_SEARCH_PARAMS)
        _, params = benchmark.parse_ntuple_spec("w.json@beam=8,samples=0,complete=1,gain_weight=20")
        self.assertEqual(params, {"beam": 8, "samples": 0, "complete": 1, "gain_weight": 20})
        with self.assertRaises(benchmark.ArmUnavailable):
            benchmark.parse_ntuple_spec("w.json@gain_weight=x")

    def test_default_is_zero(self):
        self.assertEqual(_zero_policy().gain_weight, 0)

    def test_score_weights_reject_gain_weight(self):
        with self.assertRaises(ValueError):
            NTupleLookaheadPolicy(NTupleValue(reward="score"), gain_weight=5)
        NTupleLookaheadPolicy(NTupleValue(reward="score"), gain_weight=0)

    def test_default_reproduces_pre_change_scores_beam8(self):
        """Wartość domyślna = decyzje sprzed #248 (5 seedów, sufit 4000, `complete=1`)."""
        ntuple = NTupleValue.load(WEIGHTS)
        pol = NTupleLookaheadPolicy(ntuple, beam=8, samples=0, complete=1)
        scores = []
        for seed in BASELINE_SEEDS:
            pol.reset(seed)
            game = Game(seed=seed)
            while not game.done and game.placements < 4000:
                game.step(pol.act(game, game.available_actions()))
            scores.append(game.score)
        self.assertEqual(scores, BASELINE_BEAM8_SCORES)

    def test_zero_gain_weight_is_identical_to_default(self):
        ntuple = NTupleValue.load(WEIGHTS)
        for seed in (5, 6):
            a = NTupleLookaheadPolicy(ntuple, beam=8, samples=0, complete=1)
            b = NTupleLookaheadPolicy(ntuple, beam=8, samples=0, complete=1, gain_weight=0)
            ga, gb = Game(seed=seed), Game(seed=seed)
            for _ in range(40):
                aa = a.act(ga, ga.available_actions())
                ab = b.act(gb, gb.available_actions())
                self.assertEqual(aa, ab)
                ga.step(aa)
                gb.step(ab)

    def test_native_matches_python_search(self):
        """Rdzeń natywny w skali ×1000 daje te same stany co wiązka w Pythonie."""
        ntuple = NTupleValue.load(WEIGHTS)
        if ntuple.native is None:
            self.skipTest("brak rdzenia natywnego")
        rng = random.Random(248)
        for weight in (3, 20, 250):
            pol = NTupleLookaheadPolicy(ntuple, beam=16, samples=0, gain_weight=weight)
            for seed in (11, 12):
                game = _midgame(seed, rng.randrange(10, 60))
                if game.done:
                    continue
                actions = game.available_actions()
                args = (game.board, tuple(game.pieces), game.combo, game.combo_counter)
                native, n_native = pol._search(*args, 16, root_actions=actions)
                ref, n_ref = policies._tray_beam_search(
                    *args, None, 16, root_actions=actions, leaf_value=pol._ntuple_leaf,
                    path_key="placed", gain_weight=weight,
                )
                self.assertEqual(n_native, n_ref)
                self.assertEqual(len(native), len(ref))
                for a, b in zip(native, ref):
                    self.assertEqual(a["first_action"], b["first_action"])
                    self.assertEqual(a["gain"], b["gain"])
                    self.assertEqual(a["placed"], b["placed"])
                    self.assertEqual(a["pieces"], b["pieces"])
                    self.assertAlmostEqual(a["score"], b["score"], places=6)

    def test_gain_weight_prefers_more_points_among_complete_trays(self):
        """Z zerową oceną i szeroką wiązką wybór wśród pełnych ułożeń idzie za punktami."""
        game = _midgame(21, 30)
        actions = game.available_actions()
        args = (game.board, tuple(game.pieces), game.combo, game.combo_counter)
        zero = lambda b, c, cc: 0.0
        full = policies._tray_complete_search(*args, zero, "placed", 1)
        if not full:
            self.skipTest("tacka nieukładalna w tej pozycji")
        best = max(st["gain"] for st in full)
        firsts = set(st["first_action"] for st in full if st["gain"] == best)
        pol = _zero_policy(beam=400, complete=1, gain_weight=1000)
        self.assertIn(pol.act(game, actions), firsts)

    def test_samples_path_returns_legal_action(self):
        ntuple = NTupleValue.load(WEIGHTS)
        pol = NTupleLookaheadPolicy(ntuple, beam=4, samples=2, branch=3, complete=1, gain_weight=10)
        game = _midgame(31, 20)
        pol.reset(31)
        actions = game.available_actions()
        self.assertIn(pol.act(game, actions), actions)


if __name__ == "__main__":
    unittest.main()
