"""
Testy haka wartości liścia w `policies._tray_beam_search` (#125).

Scalenie #123 na `main` ustawiło sygnaturę haka na **tę samą trójkę**, którą
przeszukanie przekazuje do `_weighted_features` po #118: `(board, combo,
combo_counter)`. Dwie rzeczy trzeba trzymać testem, bo obie da się zepsuć
niewinną zmianą:

1. Hak dostaje dokładnie te trzy argumenty i dokładnie te same wartości, które
   dostałby domyślny `_weighted_features` — inaczej alternatywne źródło
   wartości oceniałoby inny stan niż ręczne wagi i porównanie ramion kłamałoby.
2. Adapter N-tuple **ignoruje** `combo`/`combo_counter` i zwraca
   `NTupleValue.value(board)`. To jest decyzja projektowa z #125, nie skutek
   uboczny: `gain` już niesie efekt combo dla ocenianego ruchu, a jedyny pomiar
   członu combo w ocenie liścia wyszedł ujemnie (#122: −6,6%). Argumenty
   zostają w sygnaturze, żeby dosypanie combo później nie wymagało zmiany haka —
   test pilnuje, że dziś nie mają wpływu.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import policies
from board import Board
from game import Game
from ntuple import PATCH_LAYOUT, NTupleValue
from policies import HeuristicPolicy, NTupleLookaheadPolicy


def _board_with(cells):
    board = Board()
    for x, y in cells:
        board.grid[y][x] = 1
    return board


class TestLeafValueHookSignature(unittest.TestCase):
    def setUp(self):
        self.game = Game(seed=11)
        self.weights = HeuristicPolicy.DEFAULT_WEIGHTS

    def _search(self, leaf_value):
        return policies._tray_beam_search(
            self.game.board, tuple(self.game.pieces), 3, 2,
            self.weights, 4, leaf_value=leaf_value,
        )

    def test_hook_sees_the_same_triple_as_weighted_features(self):
        """Ten sam stan u haka i u domyślnej oceny — plansza, combo, licznik."""
        default_calls = []
        real = policies._weighted_features

        def recording_weighted_features(weights, board, combo, combo_counter):
            default_calls.append((tuple(map(tuple, board.grid)), combo, combo_counter))
            return real(weights, board, combo, combo_counter)

        policies._weighted_features = recording_weighted_features
        try:
            default_frontier, _ = self._search(None)
        finally:
            policies._weighted_features = real

        hook_calls = []

        def hook(board, combo, combo_counter):
            hook_calls.append((tuple(map(tuple, board.grid)), combo, combo_counter))
            return real(self.weights, board, combo, combo_counter)

        hook_frontier, _ = self._search(hook)

        self.assertTrue(default_calls, "przeszukanie nie policzyło ani jednego liścia")
        self.assertEqual(hook_calls, default_calls)
        # Ten sam stan i ta sama liczba na wyjściu znaczy tę samą wiązkę.
        self.assertEqual([c["score"] for c in hook_frontier],
                         [c["score"] for c in default_frontier])
        self.assertEqual([c["first_action"] for c in hook_frontier],
                         [c["first_action"] for c in default_frontier])

    def test_hook_is_called_with_three_positional_arguments(self):
        """Hak o dwóch argumentach ma wywalić — sygnatura jest trójką, nie parą."""
        with self.assertRaises(TypeError):
            self._search(lambda board, combo: 0.0)


class TestNTupleLeafIgnoresCombo(unittest.TestCase):
    def setUp(self):
        # Wagi różne od zera, inaczej test przeszedłby dla dowolnej oceny.
        self.ntuple = NTupleValue(weights=[
            [float((p * 31 + i) % 7) - 3.0 for i in range(1 << len(positions))]
            for p, positions in enumerate(PATCH_LAYOUT)
        ])
        self.policy = NTupleLookaheadPolicy(self.ntuple)

    def test_leaf_equals_ntuple_value_of_the_board(self):
        board = _board_with([(0, 0), (1, 0), (3, 4), (7, 7)])
        self.assertEqual(self.policy._ntuple_leaf(board, 0, 4),
                         self.ntuple.value(board))
        self.assertNotEqual(self.ntuple.value(board), 0.0)

    def test_combo_and_counter_do_not_change_the_leaf(self):
        board = _board_with([(2, 2), (2, 3), (5, 6)])
        baseline = self.policy._ntuple_leaf(board, 0, 4)
        for combo, counter in ((1, 1), (7, 3), (40, 6), (0, 1)):
            self.assertEqual(self.policy._ntuple_leaf(board, combo, counter), baseline,
                             "combo=%r licznik=%r zmieniło wartość liścia" % (combo, counter))

    def test_policy_installs_the_adapter_not_ntuple_value_directly(self):
        """`_leaf_value` musi brać trójkę — `NTupleValue.value` bierze tylko planszę."""
        self.assertEqual(self.policy._leaf_value, self.policy._ntuple_leaf)
        board = _board_with([(0, 0)])
        self.assertEqual(self.policy._leaf_value(board, 5, 2), self.ntuple.value(board))

    def test_search_through_the_policy_scores_by_ntuple(self):
        """Ścieżka od `_search` do liścia rzeczywiście idzie przez sieć."""
        game = Game(seed=5)
        frontier, _ = self.policy._search(
            game.board, tuple(game.pieces), 0, 4, 2,
        )
        self.assertTrue(frontier)
        for candidate in frontier:
            self.assertEqual(
                candidate["score"],
                candidate["gain"] + self.ntuple.value(candidate["board"]),
            )


if __name__ == "__main__":
    unittest.main()
