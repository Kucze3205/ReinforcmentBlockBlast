"""
Testy gwarancji ułożenia tacki `complete=1` w `NTupleLookaheadPolicy` (#239).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import benchmark
import policies
from game import Game
from ntuple import NTupleValue
from pieces import PIECE_POOL
from policies import NTupleLookaheadPolicy

P = {p.name: p for p in PIECE_POOL}


def _game(holes, pieces):
    """Plansza pełna poza `holes` (komórki `(x, y)`), tacka `pieces` (nazwy albo `None`)."""
    g = Game(seed=1)
    g.board.grid = [[1] * 8 for _ in range(8)]
    for x, y in holes:
        g.board.grid[y][x] = 0
    g.pieces = [P[n] if n else None for n in pieces]
    return g


def _policy(**kw):
    kw.setdefault("samples", 0)
    return NTupleLookaheadPolicy(NTupleValue(reward="survival"), **kw)


def _zero(board, combo, combo_counter):
    return 0.0


def _rest_fits(game, action):
    """Czy po `action` reszta tacki układa się w całości (przegląd wyczerpujący)."""
    root = dict(
        board=game.board, pieces=tuple(game.pieces), combo=game.combo,
        combo_counter=game.combo_counter, gain=0, placed=0, first_action=None,
    )
    state = policies._expand(root, action)
    if not any(p is not None for p in state["pieces"]):
        return True
    return bool(policies._tray_complete_search(
        state["board"], state["pieces"], state["combo"], state["combo_counter"], _zero, "placed",
    ))


class CompleteTrayTest(unittest.TestCase):
    # 2x2 w lewym górnym rogu plus pojedyncze dziury na przekątnej (żaden wiersz ani
    # kolumna nie jest pełna). Wiązka o szerokości 1
    # przy zerowej ocenie bierze pierwszą akcję w kolejności: 1x1 w (0, 0), po czym
    # 2x2 nigdzie się nie mieści.
    HOLES = [(0, 0), (1, 0), (0, 1), (1, 1)] + [(k, k) for k in range(2, 8)]
    PIECES = ("1x1", "square2", None)

    def test_narrow_beam_gets_stuck_without_guarantee(self):
        g = _game(self.HOLES, self.PIECES)
        action = _policy(beam=1).act(g, g.available_actions())
        self.assertFalse(_rest_fits(g, action))

    def test_complete_picks_move_after_which_rest_fits(self):
        g = _game(self.HOLES, self.PIECES)
        action = _policy(beam=1, complete=1).act(g, g.available_actions())
        self.assertIn(action, g.available_actions())
        self.assertTrue(_rest_fits(g, action))

    def test_complete_with_samples_also_guarantees(self):
        g = _game(self.HOLES, self.PIECES)
        pol = _policy(beam=1, samples=2, branch=4, complete=1)
        pol.reset(3)
        self.assertTrue(_rest_fits(g, pol.act(g, g.available_actions())))

    def test_unsolvable_tray_still_returns_legal_action(self):
        # 1x1 się mieści (dziury na przekątnej), kwadrat 3x3 nigdy — także po czyszczeniu.
        g = _game([(k, k) for k in range(8)], ("1x1", "square3", None))
        self.assertFalse(policies._tray_complete_search(
            g.board, tuple(g.pieces), 0, 0, _zero, "placed"))
        actions = g.available_actions()
        self.assertIn(_policy(beam=4, complete=1).act(g, actions), actions)

    def test_default_is_zero_and_param_is_known(self):
        self.assertEqual(_policy().complete, 0)
        self.assertIn("complete", benchmark.NTUPLE_SEARCH_PARAMS)
        _, params = benchmark.parse_ntuple_spec("w.json@beam=128,samples=0,complete=1")
        self.assertEqual(params, {"beam": 128, "samples": 0, "complete": 1})

    def test_complete_zero_is_identical_to_default(self):
        for seed in (5, 6):
            a, b = _policy(beam=8), _policy(beam=8, complete=0)
            ga, gb = Game(seed=seed), Game(seed=seed)
            for _ in range(15):
                if ga.done:
                    break
                aa = a.act(ga, ga.available_actions())
                ab = b.act(gb, gb.available_actions())
                self.assertEqual(aa, ab)
                ga.step(aa)
                gb.step(ab)


if __name__ == "__main__":
    unittest.main()
